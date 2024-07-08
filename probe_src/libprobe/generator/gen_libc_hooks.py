#!/usr/bin/env python3

from __future__ import annotations
import dataclasses
import re
import pycparser
import pycparser.c_generator
import typing
import tempfile
import pathlib
import collections.abc
import sys


class GccCGenerator(pycparser.c_generator.CGenerator):
    """A C generator that is able to emit gcc statement-expr ({...;})"""

    def visit_Assignment(self, n):
        rval_str = self._parenthesize_if(
            n.rvalue,
            lambda n: isinstance(n, (pycparser.c_ast.Assignment, pycparser.c_ast.Compound)),
        )
        return '%s %s %s' % (self.visit(n.lvalue), n.op, rval_str)

    def visit_Decl(self, n, no_type=False):
        s = n.name if no_type else self._generate_decl(n)
        if n.bitsize: s += ' : ' + self.visit(n.bitsize)
        if n.init:
            s += ' = ' + self._parenthesize_if(n.init, lambda n: isinstance(n, (pycparser.c_ast.Assignment, pycparser.c_ast.Compound)))
        return s

    def _parenthesize_if(self, n, condition):
        self.indent_level += 2
        s = self._visit_expr(n)
        self.indent_level -= 2
        if condition(n):
            if isinstance(n, pycparser.c_ast.Compound):
                return "(\n" + s + self._make_indent() + ")"
            else:
                return '(' + s + ')'
        else:
            return s


def is_void(node: pycparser.c_ast.Node) -> bool:
    return isinstance(node.type, pycparser.c_ast.IdentifierType) and node.type.names[0] == "void"


def define_var(var_type: pycparser.c_ast.Node, var_name: str, value: pycparser.c_ast.Node) -> pycparser.c_ast.Decl:
    return pycparser.c_ast.Decl(
        name=var_name,
        quals=[],
        align=[],
        storage=[],
        funcspec=[],
        type=pycparser.c_ast.TypeDecl(
            declname=var_name,
            quals=[],
            align=None,
            type=var_type,
        ),
        init=value,
        bitsize=None,
    )


void = pycparser.c_ast.IdentifierType(names=['void'])

c_ast_int = pycparser.c_ast.IdentifierType(names=['int'])


def ptr_type(type: pycparser.c_ast.Node) -> pycparser.c_ast.PtrDecl:
    return pycparser.c_ast.PtrDecl(
        quals=[],
        type=pycparser.c_ast.TypeDecl(
            declname="v",
            quals=[],
            align=None,
            type=type,
        ),
    )


void_fn_ptr = pycparser.c_ast.Typename(
    name=None,
    quals=[],
    align=None,
    type=pycparser.c_ast.PtrDecl(
        quals=[],
        type=pycparser.c_ast.FuncDecl(
            args=None,
            type=pycparser.c_ast.TypeDecl(
                declname=None,
                quals=[],
                align=None,
                type=void,
            ),
        ),
    ),
)


@dataclasses.dataclass(frozen=True)
class ParsedFunc:
    name: str
    # Using tuples rather than lists since tuples are covariant
    params: typing.Sequence[tuple[str, pycparser.c_ast.Node]]
    return_type: pycparser.c_ast.Node
    variadic: bool = False
    stmts: typing.Sequence[pycparser.c_ast.Node] = ()

    @staticmethod
    def from_decl(decl: pycparser.c_ast.Decl) -> ParsedFunc:
        return ParsedFunc(
            name=decl.name,
            params=tuple(
                (param_decl.name, param_decl.type)
                for param_decl in decl.type.args.params
                if isinstance(param_decl, pycparser.c_ast.Decl)
            ),
            return_type=decl.type.type,
            variadic=isinstance(decl.type.args.params[-1], pycparser.c_ast.EllipsisParam),
        )

    @staticmethod
    def from_defn(func_def: pycparser.c_ast.FuncDef) -> ParsedFunc:
        return dataclasses.replace(
            ParsedFunc.from_decl(func_def.decl),
            stmts=tuple(func_def.body.block_items) if func_def.body.block_items is not None else (),
        )

    def declaration(self) -> pycparser.c_ast.FuncDecl:
        return pycparser.c_ast.FuncDecl(
            args=pycparser.c_ast.ParamList(
                params=[
                    pycparser.c_ast.Decl(
                        name=param_name,
                        quals=[],
                        align=[],
                        storage=[],
                        funcspec=[],
                        type=param_type,
                        init=None,
                        bitsize=None,
                    )
                    for param_name, param_type in self.params
                ] + ([pycparser.c_ast.EllipsisParam()] if self.variadic else []),
            ),
            type=pycparser.c_ast.TypeDecl(
                declname=self.name,
                quals=[],
                align=[],
                type=self.return_type,
            ),
        )

    def definition(self) -> pycparser.c_ast.FuncDef:
        return pycparser.c_ast.FuncDef(
            decl=pycparser.c_ast.Decl(
                name=self.name,
                quals=[],
                align=[],
                storage=[],
                funcspec=[],
                type=self.declaration(),
                init=None,
                bitsize=None
            ),
            param_decls=None,
            body=pycparser.c_ast.Compound(
                block_items=self.stmts,
            ),
        )


filename = pathlib.Path("generator/libc_hooks_source.c")
ast = pycparser.parse_file(filename, use_cpp=True)
orig_funcs = {
    node.decl.name: ParsedFunc.from_defn(node)
    for node in ast.ext
    if isinstance(node, pycparser.c_ast.FuncDef)
}
funcs = {
    **orig_funcs,
    **{
        node.name: dataclasses.replace(orig_funcs[node.init.name], name=node.name)
        for node in ast.ext
        if isinstance(node, pycparser.c_ast.Decl) and isinstance(node.type, pycparser.c_ast.TypeDecl) and node.type.type.names == ["fn"]
    },
}
# funcs = {
#     key: val
#     for key, val in list(funcs.items())
# }
func_prefix = "unwrapped_"
func_pointer_declarations = [
    pycparser.c_ast.Decl(
        name=func_prefix + func_name,
        quals=[],
        align=[],
        storage=["static"],
        funcspec=[],
        type=pycparser.c_ast.PtrDecl(
            quals=[],
            type=dataclasses.replace(func, name=func_prefix + func.name).declaration(),
        ),
        init=None,
        bitsize=None,
    )
    for func_name, func in funcs.items()
]
init_function_pointers = ParsedFunc(
    name="init_function_pointers",
    params=(),
    return_type=void,
    variadic=False,
    stmts=[
        pycparser.c_ast.Assignment(
            op='=',
            lvalue=pycparser.c_ast.ID(name=func_prefix + func_name),
            rvalue=pycparser.c_ast.FuncCall(
                name=pycparser.c_ast.ID(name="dlsym"),
                args=pycparser.c_ast.ExprList(
                    exprs=[
                        pycparser.c_ast.ID(name="RTLD_NEXT"),
                        pycparser.c_ast.Constant(type="string", value='"' + func_name + '"'),
                    ],
                ),
            ),
        )
        for func_name, func in funcs.items()
    ],
).definition()


T = typing.TypeVar("T")
def raise_(exception: Exception) -> typing.NoReturn:
    raise exception


def raise_thunk(exception: Exception) -> typing.Callable[..., typing.NoReturn]:
    return lambda *args, **kwarsg: raise_(exception)


def find_decl(
        block: typing.Sequence[pycparser.c_ast.Node],
        name: str,
        comment: typing.Any,
) -> pycparser.c_ast.Decl | None:
    relevant_stmts = [
        stmt
        for stmt in block
        if isinstance(stmt, pycparser.c_ast.Decl) and stmt.name == name
    ]
    if not relevant_stmts:
        None
    elif len(relevant_stmts) > 1:
        raise ValueError(f"Multiple definitions of {name}" + " ({})".format(comment) if comment else "")
    else:
        return relevant_stmts[0]


def wrapper_func_body(func: ParsedFunc) -> typing.Sequence[pycparser.c_ast.Node]:
    pre_call_stmts = [
        pycparser.c_ast.FuncCall(
            name=pycparser.c_ast.ID(name="maybe_init_thread"),
            args=pycparser.c_ast.ExprList(exprs=[]),
        ),
    ]
    post_call_stmts = []

    pre_call_action = find_decl(func.stmts, "pre_call", func.name)
    if pre_call_action:
        if isinstance(pre_call_action.init, pycparser.c_ast.Compound):
            pre_call_stmts.extend(pre_call_action.init.block_items)
        else:
            pre_call_stmts.append(pre_call_action.init);

    prov_log_is_enabled = pycparser.c_ast.FuncCall(
        name=pycparser.c_ast.ID(name="prov_log_is_enabled"),
        args=pycparser.c_ast.ExprList(exprs=[]),
    )

    post_call_action = find_decl(func.stmts, "post_call", func.name)

    if post_call_action:
        post_call_stmts.extend(
            post_call_action.init.block_items,
        )

    call_stmts_block = find_decl(func.stmts, "call", func.name)
    if call_stmts_block is None:
        if func.variadic:
            varargs_size_decl = find_decl(func.stmts, "varargs_size", func.name)
            pre_call_stmts.append(varargs_size_decl)
            # Generates: __builtin_apply((void (*)())_o_open, __builtin_apply_args(), varargs_size)
            uncasted_func_call = pycparser.c_ast.FuncCall(
                name=pycparser.c_ast.ID(name="__builtin_apply"),
                args=pycparser.c_ast.ExprList(
                    exprs=[
                        pycparser.c_ast.Cast(
                            to_type=void_fn_ptr,
                            expr=pycparser.c_ast.ID(name=func_prefix + func.name)
                        ),
                        pycparser.c_ast.FuncCall(name=pycparser.c_ast.ID(name="__builtin_apply_args"), args=None),
                        pycparser.c_ast.ID(name="varargs_size"),
                    ],
                ),
            )
            if is_void(func.return_type):
                call_stmts = [uncasted_func_call]
            else:
                call_stmts = [define_var(
                    func.return_type,
                    "ret",
                    pycparser.c_ast.UnaryOp(
                        op="*",
                        expr=pycparser.c_ast.Cast(
                            to_type=ptr_type(func.return_type),
                            expr=uncasted_func_call,
                        ),
                    ),
                )]
        else:
            call_expr = pycparser.c_ast.FuncCall(
                name=pycparser.c_ast.ID(
                    name=func_prefix + func.name,
                ),
                args=pycparser.c_ast.ExprList(
                    exprs=[
                        pycparser.c_ast.ID(name=param_name)
                        for param_name, _ in func.params
                    ],
                ),
            )
            if is_void(func.return_type):
                call_stmts = [call_expr]
            else:
                call_stmts = [define_var(func.return_type, "ret", call_expr)]
    else:
        call_stmts = call_stmts_block.init.block_items

    save_errno = define_var(c_ast_int, "saved_errno", pycparser.c_ast.ID(name="errno"))
    restore_errno = pycparser.c_ast.Assignment(
        op='=',
        lvalue=pycparser.c_ast.ID(name="errno"),
        rvalue=pycparser.c_ast.ID(name="saved_errno"),
    )

    if post_call_stmts:
        post_call_stmts.insert(0, save_errno)
        post_call_stmts.append(restore_errno)

    if not is_void(func.return_type):
        post_call_stmts.append(
            pycparser.c_ast.Return(expr=pycparser.c_ast.ID(name="ret"))
        )

    return pre_call_stmts + call_stmts + post_call_stmts


static_args_wrapper_func_declarations = [
    dataclasses.replace(
        func,
        stmts=wrapper_func_body(func),
    ).definition()
    for _, func in funcs.items()
]
pathlib.Path("generated/libc_hooks.h").write_text(
    GccCGenerator().visit(
        pycparser.c_ast.FileAST(ext=[
            *func_pointer_declarations,
        ])
    )
)
pathlib.Path("generated/libc_hooks.c").write_text(
    GccCGenerator().visit(
        pycparser.c_ast.FileAST(ext=[
            init_function_pointers,
            *static_args_wrapper_func_declarations,
        ])
    )
)
