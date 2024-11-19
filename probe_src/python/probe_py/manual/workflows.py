from probe_py.manual.analysis import ProcessNode, FileNode
import networkx as nx # type: ignore
import abc
from typing import List, Set, Optional
import pathlib

"""
All the cases we should take care of:
1- One Input, One Output
2- One Input, Multiple Outputs
3- Multiple Inputs, One Output
4- Multiple Inputs, Multiple Outputs
5- Chained Commands: Inline commands that directly modify the input file (e.g., using sed, awk, or similar) 
6- No Input Command: Commands like ls .: Commands that don't take an explicit input file but generate output 
7- Ensure that any environment variables or context-specific settings are captured and translated into the Nextflow environment
8- File and Directory Structure Assumptions (Scripts that assume a specific directory structure, Commands that change the working directory (cd))
...
"""
class WorkflowGenerator(abc.ABC):
    @abc.abstractmethod
    def generate_workflow(self, graph: nx.DiGraph) -> str:
        pass

class NextflowGenerator(WorkflowGenerator):
    def __init__(self) -> None:
        self.visited: Set[ProcessNode] = set()
        self.process_counter: dict[ProcessNode, int] = {} 
        self.nextflow_script: list[str] = []  
        self.workflow: list[str] = []

    def escape_filename_for_nextflow(self, filename: str) -> str:
        """
        Escape special characters in a filename for Nextflow.
        Replace any non-letter, non-number character with _i, where i is the ASCII character code in hex.
        Additionally, escape underscores and prepend an escape code if the filename starts with a number.
        """
        escaped_filename = []

        for char in filename:
            if char.isalnum():  # Keep letters and numbers unchanged
                escaped_filename.append(char)
            else:  # Replace other characters with their ASCII code in hex
                escaped_filename.append(f'_{ord(char):02x}')

        # Ensure the filename doesn't start with a number by prepending an escape code
        if escaped_filename and escaped_filename[0].isdigit():
            escaped_filename.insert(0, '_num_')

        return ''.join(escaped_filename)


    def handle_standard_case(self, process: ProcessNode, inputs: List[FileNode], outputs: List[FileNode]) -> str:
        input_files = " ".join([f'path "{file.file}"\n   ' for file in inputs])
        output_files = " ".join([f'path "{file.file}"\n   ' for file in outputs])
        
        return f"""
process process_{id(process)} {{
    input:
    {input_files}

    output:
    {output_files}

    script:
    \"\"\"
    {' '.join(process.cmd)}
    \"\"\"
}}"""

    def handle_dynamic_filenames(self, process: ProcessNode, inputs: List[FileNode], outputs: List[FileNode]) -> str:
        input_files = " ".join([f'path "{file.file}"\n   ' for file in inputs])
        output_files = " ".join([f'path "{file.file}"\n   ' for file in outputs if file.file])

        return f"""
process process_{id(process)} {{
    input:
    {input_files}

    output:
    {output_files}

    script:
    \"\"\"
    {' '.join(process.cmd)}
    \"\"\"
}}"""

    def handle_parallel_execution(self, process: ProcessNode) -> str:
        input_files = "splitFile"
        output_files = "outputFile"
        return f"""
process process_{id(process)} {{
    input:
    "{input_files}"

    output:
    "{output_files}"

    script:
    \"\"\"
    {' '.join(process.cmd)}
    \"\"\"
}}
splitFile = Channel.fromPath('inputFiles/*').splitText()
process_{id(process)} (splitFile.collect())"""

    def handle_custom_shells(self, process: ProcessNode) -> str:
        return f"""
process process_{id(process)} {{
    output:
        stdout
    
    script:
    \"\"\"
    {' '.join(process.cmd)}
    \"\"\"
}}"""



    def is_standard_case(self, process: ProcessNode, inputs: List[FileNode], outputs: List[FileNode]) -> bool:
        return len(inputs) >= 1 and len(outputs) == 1

    def is_multiple_output_case(self, process: ProcessNode, inputs: List[FileNode], outputs: List[FileNode]) -> bool:
        return len(inputs) >= 1 and len(outputs) >= 1
    
    def is_dynamic_filename_case(self, process: ProcessNode, outputs: List[FileNode]) -> bool:
        return any("*" in file.file or "v*" in file.file for file in outputs if file.file)

    def is_parallel_execution(self, process: ProcessNode) -> bool:
        return len(process.cmd) > 1 and "parallel" in process.cmd

    def create_processes(self) -> None:
        """
        Create Nextflow processes based on the dataflow graph.
        """
        for node in self.graph.nodes:
            if isinstance(node, ProcessNode) and node not in self.visited:
                inputs = [n for n in self.graph.predecessors(node) if isinstance(n, FileNode)]
                outputs = [n for n in self.graph.successors(node) if isinstance(n, FileNode)]

                if self.is_standard_case(node, inputs, outputs) :
                    process_script = self.handle_standard_case(node, inputs, outputs)
                    self.nextflow_script.append(process_script)
                    self.workflow.append(f"{self.escape_filename_for_nextflow(outputs[0].label)} = process_{id(node)}({', '.join([self.escape_filename_for_nextflow(i.label) for i in inputs])})")
                elif self.is_multiple_output_case(node,inputs,outputs) : 
                    raise NotImplementedError("Handling multiple outputs not implemented yet.")
                elif self.is_dynamic_filename_case(node, outputs):
                    process_script = self.handle_dynamic_filenames(node, inputs, outputs)
                elif self.is_parallel_execution(node):
                    process_script = self.handle_parallel_execution(node)
                else:
                    process_script = self.handle_custom_shells(node)
                    self.nextflow_script.append(process_script)
                    self.workflow.append(f"process_{id(node)}()")

                self.visited.add(node)
  
    def generate_workflow(self, graph: nx.DiGraph) -> str:  
        """
        Generate the complete Nextflow workflow script from the graph.
        """
        self.graph = graph
        self.nextflow_script.append("nextflow.enable.dsl=2\n\n")
        self.create_processes()

        # Append the workflow section
        self.nextflow_script.append("\nworkflow {\n")

        # Add file nodes to the script
        filenames = set()
        for node in self.graph.nodes:
            if isinstance(node, FileNode):
                escaped_name = self.escape_filename_for_nextflow(node.label)
                if node.inodeOnDevice not in filenames:
                    if pathlib.Path(node.file).exists():
                        self.nextflow_script.append(f"  {escaped_name}=file(\"{node.file}\")")
                        filenames.add(node.inodeOnDevice)

        
        for step in self.workflow:
            self.nextflow_script.append(f"  {step}")
        self.nextflow_script.append("}")

        return "\n".join(self.nextflow_script)


class MakefileGenerator:
    def __init__(self, output_dir: str = "experiments") -> None:
        self.visited: Set[ProcessNode] = set()
        self.makefile_commands: list[str] = []
        self.output_dir = output_dir

    def escape_filename_for_makefile(self, filename: str) -> str:
        """
        Escape special characters in a filename for Makefile.
        Replace spaces and other special characters with underscores.
        """
        return filename.replace(" ", "_").replace("(", "_").replace(")", "_").replace(",", "_")

    def is_hidden_file(self, filename: str) -> bool:
        """
        Determine if a file is hidden.
        Hidden files start with '.' or '._'.
        """
        return filename.startswith('.') or filename.startswith('._')

    def create_experiment_folder_command(self, process: ProcessNode) -> str:
        """
        Generate the command to create a folder for the experiment.
        """
        folder_name = f"process_{id(ProcessNode)}"
        return f"mkdir -p {folder_name}"

    def copy_input_files_command(self, process: ProcessNode, inputs: List[FileNode]) -> Optional[str]:
        """
        Generate the command to copy input files into the experiment folder.
        Returns None if there are no input files.
        """
        if not inputs:
            return None

        folder_name = f"process_{id(ProcessNode)}"
        commands = []
        for file in inputs:
            if self.is_hidden_file(file.label):
                continue  # Skip hidden files
            escaped_file = self.escape_filename_for_makefile(file.label)
            commands.append(f"cp {escaped_file} {folder_name}/")
        
        if commands:
            return "\n\t".join(commands)
        return None

    def run_command_command(self, process: ProcessNode, outputs: List[FileNode]) -> str:
        """
        Generate the command to run the experiment's command within the experiment folder.
        Redirect stdout and stderr to log files if outputs are not files.
        """
        folder_name = f"process_{id(ProcessNode)}"
        cmd = " ".join(process.cmd)
        if not outputs:
            # No output files, redirect to log
            return f"({cmd}) > {folder_name}/output.log 2>&1"
        else:
            # Execute command within the folder
            return f"(cd {folder_name} && {cmd})"

    def handle_process_node(self, process: ProcessNode, inputs: List[FileNode], outputs: List[FileNode]) -> None:
        """
        Generate all necessary Makefile commands for a given process node.
        Handles different cases based on presence of inputs and outputs.
        """
        # Create experiment folder
        self.makefile_commands.append(f"# Process {id(ProcessNode)}: {' '.join(process.cmd)}")
        self.makefile_commands.append(f"\tmkdir -p process_{id(ProcessNode)}")
        
        # Copy input files
        copy_inputs = self.copy_input_files_command(process, inputs)
        if copy_inputs:
            self.makefile_commands.append(f"# Copy input files for process {id(ProcessNode)}")
            self.makefile_commands.append(f"\t{copy_inputs}")
        
        # Run the command
        self.makefile_commands.append(f"# Run command for process {id(ProcessNode)}")
        run_cmd = self.run_command_command(process, outputs)
        self.makefile_commands.append(f"\t{run_cmd}")
        
        # No copying of output files since they are inside the folder

    def create_rules(self) -> None:
        """
        Traverse the graph and create Makefile commands.
        """
        # Ensure the output directory exists
        self.makefile_commands.append(f"\tmkdir -p {self.output_dir}\n")
        
        # Traverse the graph in topological order to respect dependencies
        for node in nx.topological_sort(self.graph):
            if isinstance(node, ProcessNode):
                inputs = [n for n in self.graph.predecessors(node) if isinstance(n, FileNode)]
                outputs = [n for n in self.graph.successors(node) if isinstance(n, FileNode)]
                
                self.handle_process_node(node, inputs, outputs)

    def generate_makefile(self, graph: nx.DiGraph) -> str:
        """
        Generate the complete Makefile script from the graph.
        """
        self.graph = graph
        self.create_rules()
        
        # Assemble the Makefile
        makefile = []
        makefile.append("all:")
        for command in self.makefile_commands:
            # Ensure each command line is properly indented with a tab
            # Makefile syntax requires tabs, not spaces
            makefile.append(f"\t{command}")
        
        return "\n".join(makefile)