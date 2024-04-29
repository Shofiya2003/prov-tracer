/*
 * This file looks like C, but it is not read by the C compiler!
 * It is a place-holder for C code and is processed by gen_libprov.py and put into libprov_middle.c.
 * It re-uses C's grammar, so I get syntax highlighting and I can parse it into fragments of C syntax easily.
 * Rationale: In this part of the project, there are many repetitions of code automatically generated.
 * For example, for each function $foo, we define a wrapper function $foo that calls the original function o_$foo with the same arguments.
 * Just read libprov_middle.c.
 * I can more easily refactor how it works if I don't have to edit each individual instance.
 * gen_libprov.py reads the function signatures, and inside the function bodies, it looks for some specific variable declarations of the form: Type var_name = var_val;
 * We use GCC block-expressions to communicate blocks of code to gen_libprov.py: ({stmt0; stmt1; ...; }).
 */

/* Need these typedefs to make pycparser parse the functions. They won't be used in libprov_middle.c */
typedef void* FILE;
typedef void* DIR;
typedef void* pid_t;
typedef void* mode_t;
typedef void* __ftw_func_t;
typedef void* __ftw64_func_t;
typedef void* __nftw_func_t;
typedef void* __nftw64_func_t;
typedef void* size_t;
typedef void* ssize_t;
typedef void* off_t;
typedef void* off64_t;
typedef void* dev_t;
typedef void* uid_t;
typedef void* gid_t;
typedef int bool;
struct stat;
struct stat64;
struct utimebuf;
typedef void* Path;
typedef void* OpCode;
typedef void* fn;
typedef void* va_list;
struct Path;
struct utimbuf;
struct dirent;
int __type_mode_t;

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Opening-Streams.html */
FILE * fopen (const char *filename, const char *opentype) {
    void* pre_call = ({
        char* path = NULL;
        if (prov_log_is_enabled()) {
            path = normalize_path(path, AT_FDCWD, filename);
            prov_log_record(make_op(MetadataRead, path, null_fd, null_mode));
        }
    });
    void* post_call = ({
        if (prov_log_is_enabled() && ret != NULL) {
            prov_log_record(make_op(fopen_to_opcode(opentype), strndup(path, PATH_MAX), fileno(ret), null_mode));
            fd_table_associate(fileno(ret), path);
        }
    });
}
fn fopen64 = fopen;
FILE * freopen (const char *filename, const char *opentype, FILE *stream) {
    void* pre_call = ({
        char* path = NULL;
        int original_fd = null_fd;
        if (prov_log_is_enabled()) {
            path = normalize_path(path, AT_FDCWD, filename);
            original_fd = fileno(stream);
            prov_log_record(make_op(MetadataRead, path, null_fd, null_mode));
        }
    });
    void* post_call = ({
        if (prov_log_is_enabled()) {
            if (ret != NULL) {
                prov_log_record(make_op(Close, null_path, original_fd, null_mode));
                prov_log_record(make_op(fopen_to_opcode(opentype), strndup(path, PATH_MAX), fileno(ret), null_mode));
                fd_table_associate(fileno(ret), path);
            } else {
                fprintf(stderr, "Don't know how to handle the case where freopen fails. Does it fail during close, the open, or both?\n");
                abort();
            }
        }
    });
}
fn freopen64 = freopen;

/* Need: In case an analysis wants to use open-to-close consistency */
/* Docs: https://www.gnu.org/software/libc/manual/html_node/Closing-Streams.html */
int fclose (FILE *stream) {
    void* pre_call = ({
        int original_fd = fileno(stream);
    });
    void* post_call = ({
        if (prov_log_is_enabled() && ret == 0) {
            prov_log_record(make_op(Close, null_path, original_fd, null_mode));
            fd_table_close(original_fd);
        }
    });
}
int fcloseall(void) {
    void* post_call = ({
        if (prov_log_is_enabled() && ret == 0) {
            size_t upper_limit = fd_table_size();
            for (size_t fd = 0; fd < upper_limit; ++fd) {
                prov_log_record(make_op(Close, null_path, fd, null_mode));
                fd_table_close(fd);
            }
        }
    });
}

/* Docs: https://linux.die.net/man/2/openat */
int openat(int dirfd, const char *pathname, int flags, ...) {
    size_t varargs_size = sizeof(dirfd) + sizeof(pathname) + sizeof(flags) + (has_mode_arg ? sizeof(mode_t) : 0);
    /* Re varag_size, See variadic note on open
     * https://github.com/bminor/glibc/blob/2367bf468ce43801de987dcd54b0f99ba9d62827/sysdeps/unix/sysv/linux/open64.c#L33
     */
    void* pre_call = ({
        char* path = NULL;
        bool has_mode_arg = (flags & O_CREAT) != 0 || (flags & __O_TMPFILE) == __O_TMPFILE;
        mode_t mode_arg = null_mode;
        if (prov_log_is_enabled()) {
            path = normalize_path(path, dirfd, pathname);
            if (has_mode_arg) {
                va_list ap;
                va_start(ap, flags);
                mode_arg = va_arg(ap, __type_mode_t);
                va_end(ap);
            }
            prov_log_record(make_op(MetadataRead, path, null_fd, mode_arg));
        }
    });
    void* post_call = ({
        if (prov_log_is_enabled() && ret != -1) {
            prov_log_record(make_op(open_flag_to_opcode(flags), strndup(path, PATH_MAX), ret, mode_arg));
            fd_table_associate(ret, path);
        }
    });
}

fn openat64 = openat;

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Opening-and-Closing-Files.html */
int open (const char *filename, int flags, ...) {
    size_t varargs_size = sizeof(filename) + sizeof(flags) + (has_mode_arg ? sizeof(mode_t) : 0);
    /* Re varag_size
     * We use the third-arg (of type mode_t) when ((flags) & O_CREAT) != 0 || ((flags) & __O_TMPFILE) == __O_TMPFILE.
     * https://github.com/bminor/glibc/blob/2367bf468ce43801de987dcd54b0f99ba9d62827/sysdeps/unix/sysv/linux/openat.c#L33
     * https://github.com/bminor/glibc/blob/2367bf468ce43801de987dcd54b0f99ba9d62827/sysdeps/unix/sysv/linux/open.c#L35
     * https://github.com/bminor/glibc/blob/2367bf468ce43801de987dcd54b0f99ba9d62827/io/fcntl.h#L40
     */
    void* pre_call = ({
        char* path = NULL;
        bool has_mode_arg = (flags & O_CREAT) != 0 || (flags & __O_TMPFILE) == __O_TMPFILE;
        mode_t mode_arg = null_mode;
        if (prov_log_is_enabled()) {
            if (has_mode_arg) {
                va_list ap;
                va_start(ap, flags);
                mode_arg = va_arg(ap, __type_mode_t);
                va_end(ap);
            }
            path = normalize_path(path, AT_FDCWD, filename);
            prov_log_record(make_op(MetadataRead, path, null_fd, mode_arg));
        }
    });
    void* post_call = ({
        if (prov_log_is_enabled() && ret != -1) {
            prov_log_record(make_op(open_flag_to_opcode(flags), strndup(path, PATH_MAX), ret, mode_arg));
            fd_table_associate(ret, path);
        }
    });
}
fn open64 = open;
int creat (const char *filename, mode_t mode) {
    void* pre_call = ({
        char* path = NULL;
        if (prov_log_is_enabled()) {
            path = normalize_path(path, AT_FDCWD, filename);
            prov_log_record(make_op(MetadataRead, path, null_fd, null_mode));
        }
    });
    void* post_call = ({
        if (prov_log_is_enabled() && ret != -1) {
            /* TODO: check that this should be open with writepart */
            prov_log_record(make_op(OpenWritePart, strndup(path, PATH_MAX), ret, mode));
            fd_table_associate(ret, path);
        }
    });
}
fn create64 = creat;
int close (int filedes) {
    void* post_call = ({
         if (prov_log_is_enabled() && ret == 0) {
            prov_log_record(make_op(Close, null_path, filedes, null_mode));
            fd_table_close(filedes);
        }
    });
}
int close_range (unsigned int lowfd, unsigned int maxfd, int flags) {
    void* post_call = ({
        if (prov_log_is_enabled() && ret == 0) {
            size_t maxfd = fd_table_size();
            for (size_t fd = lowfd; fd < maxfd; ++fd) {
                if (fd_table_is_used(fd)) {
                    fd_table_close(fd);
                    prov_log_record(make_op(Close, null_path, fd, null_mode));
                }
            }
        } else {
            fprintf(stderr, "Don't know what to do when close_range fails\n");
            /* Does it close part of the range or none of it? */
            abort();
        }
    });
}
void closefrom (int lowfd) {
    void* post_call = ({
        if (prov_log_is_enabled()) {
            size_t maxfd = fd_table_size();
            for (size_t fd = lowfd; fd < maxfd; ++fd) {
                if (fd_table_is_used(fd)) {
                    fd_table_close(fd);
                    prov_log_record(make_op(Close, null_path, fd, null_mode));
                }
            }
        }
    });
}

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Duplicating-Descriptors.html */
int dup (int old) { }
int dup2 (int old, int new) { }

/* Docs: https://www.man7.org/linux/man-pages/man2/dup.2.html */
int dup3 (int old, int new) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Control-Operations.html#index-fcntl-function */
int fcntl (int filedes, int command, ...) {
    void* pre_call = ({
            bool int_arg = command == F_DUPFD || command == F_DUPFD_CLOEXEC || command == F_SETFD || command == F_SETFL || command == F_SETOWN || command == F_SETSIG || command == F_SETLEASE || command == F_NOTIFY || command == F_SETPIPE_SZ || command == F_ADD_SEALS;
            bool ptr_arg = command == F_SETLK || command == F_SETLKW || command == F_GETLK || /* command == F_OLD_SETLK || command == F_OLD_SETLKW || command == F_OLD_GETLK || */ command == F_GETOWN_EX || command == F_SETOWN_EX || command == F_GET_RW_HINT || command == F_SET_RW_HINT || command == F_GET_FILE_RW_HINT || command == F_SET_FILE_RW_HINT;
            /* Highlander assertion: there can only be one! */
            /* But there could be zero, as in fcntl(fd, F_GETFL) */
            assert(!int_arg || !ptr_arg);
        });
    size_t varargs_size = sizeof(filedes) + sizeof(command) + (
        int_arg ? sizeof(int)
        : ptr_arg ? sizeof(void*)
        : 0
    );
    /* Variadic:
     * https://www.man7.org/linux/man-pages/man2/fcntl.2.html
     * "The required argument type is indicated in parentheses after each cmd name" */
}

/* Need: We need this so that opens relative to the current working directory can be resolved */
/* Docs: https://www.gnu.org/software/libc/manual/html_node/Working-Directory.html */
int chdir (const char *filename) {
    void* pre_call = ({
        char* path = NULL;
        if (prov_log_is_enabled()) {
            path = normalize_path(path, AT_FDCWD, filename);
            prov_log_record(make_op(Chdir, path, null_fd, null_mode));
        }
    });
    void* post_call = ({
        if (prov_log_is_enabled()) {
            track_chdir(path);
        }
    });
}
int fchdir (int filedes) {
    void* pre_call = ({
        char* path = NULL;
        if (prov_log_is_enabled()) {
            path = normalize_path(path, filedes, NULL);
            prov_log_record(make_op(Chdir, path, null_fd, null_mode));
        }
    });
    void* post_call = ({
        if (prov_log_is_enabled()) {
            track_chdir(path);
        }
    });
}

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Opening-a-Directory.html */
DIR * opendir (const char *dirname) {
    void* pre_call = ({
        char* path = NULL;
        if (prov_log_is_enabled()) {
            path = normalize_path(path, AT_FDCWD, dirname);
            prov_log_record(make_op(MetadataRead, path, null_fd, null_mode));
        }
    });
    void* post_call = ({
        if (prov_log_is_enabled() && ret != NULL) {
            int fd = dirfd(ret);
            prov_log_record(make_op(OpenDir, strndup(path, PATH_MAX), fd, null_mode));
            fd_table_associate(fd, path);
        }
    });
}
DIR * fdopendir (int fd) {
    void* pre_call = ({
        char* path = NULL;
        if (prov_log_is_enabled()) {
            path = normalize_path(path, fd, NULL);
            prov_log_record(make_op(MetadataRead, path, null_fd, null_mode));
        }
    });
    void* post_call = ({
        if (prov_log_is_enabled() && ret != NULL) {
            int fd = dirfd(ret);
            prov_log_record(make_op(OpenDir, strndup(path, PATH_MAX), fd, null_mode));
            fd_table_associate(fd, path);
        }
    });
}

/* https://www.gnu.org/software/libc/manual/html_node/Reading_002fClosing-Directory.html */
struct dirent * readdir (DIR *dirstream) { }
int readdir_r (DIR *dirstream, struct dirent *entry, struct dirent **result) { }
struct dirent64 * readdir64 (DIR *dirstream) { }
int readdir64_r (DIR *dirstream, struct dirent64 *entry, struct dirent64 **result) { }
int closedir (DIR *dirstream) { }

/* https://www.gnu.org/software/libc/manual/html_node/Random-Access-Directory.html */
void rewinddir (DIR *dirstream) { }
long int telldir (DIR *dirstream) { }
void seekdir (DIR *dirstream, long int pos) { }

/* https://www.gnu.org/software/libc/manual/html_node/Scanning-Directory-Content.html */
int scandir (const char *dir, struct dirent ***namelist, int (*selector) (const struct dirent *), int (*cmp) (const struct dirent **, const struct dirent **)) { }
int scandir64 (const char *dir, struct dirent64 ***namelist, int (*selector) (const struct dirent64 *), int (*cmp) (const struct dirent64 **, const struct dirent64 **)) { }

/* https://www.gnu.org/software/libc/manual/html_node/Low_002dlevel-Directory-Access.html */
ssize_t getdents64 (int fd, void *buffer, size_t length) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Working-with-Directory-Trees.html */
/* Need: These operations walk a directory recursively */
int ftw (const char *filename, __ftw_func_t func, int descriptors) { }
int ftw64 (const char *filename, __ftw64_func_t func, int descriptors) { }
int nftw (const char *filename, __nftw_func_t func, int descriptors, int flag) { }
int nftw64 (const char *filename, __nftw64_func_t func, int descriptors, int flag) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Hard-Links.html */
int link (const char *oldname, const char *newname) { }
int linkat (int oldfd, const char *oldname, int newfd, const char *newname, int flags) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Symbolic-Links.html */
int symlink (const char *oldname, const char *newname) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Symbolic-Links.html */
int symlinkat(const char *target, int newdirfd, const char *linkpath) { }
ssize_t readlink (const char *filename, char *buffer, size_t size) { }
ssize_t readlinkat (int dirfd, const char *filename, char *buffer, size_t size) { }
char * canonicalize_file_name (const char *name) { }
char * realpath (const char *restrict name, char *restrict resolved) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Deleting-Files.html */
int unlink (const char *filename) { }
int rmdir (const char *filename) { }
int remove (const char *filename) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Renaming-Files.html */
int rename (const char *oldname, const char *newname) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Creating-Directories.html */
int mkdir (const char *filename, mode_t mode) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Reading-Attributes.html */
int stat (const char *filename, struct stat *buf) { }
int stat64 (const char *filename, struct stat64 *buf) { }
int fstat (int filedes, struct stat *buf) { }
int fstat64 (int filedes, struct stat64 *buf) { }
int lstat (const char *filename, struct stat *buf) { }
int lstat64 (const char *filename, struct stat64 *buf) { }

/* Docs: https://www.man7.org/linux/man-pages/man2/statx.2.html */
int statx(int dirfd, const char *restrict pathname, int flags, unsigned int mask, struct statx *restrict statxbuf) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/File-Owner.html */
int chown (const char *filename, uid_t owner, gid_t group) { }
int fchown (int filedes, uid_t owner, gid_t group) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Setting-Permissions.html  */
int chmod (const char *filename, mode_t mode) { }
int fchmod (int filedes, mode_t mode) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Testing-File-Access.html */
int access (const char *filename, int how) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/File-Times.html */
int utime (const char *filename, const struct utimbuf *times) { }
int utimes (const char *filename, const struct timeval tvp[2]) { }
int lutimes (const char *filename, const struct timeval tvp[2]) { }
int futimes (int fd, const struct timeval tvp[2]) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/File-Size.html */
int truncate (const char *filename, off_t length) { }
int truncate64 (const char *name, off64_t length) { }
int ftruncate (int fd, off_t length) { }
int ftruncate64 (int id, off64_t length) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Making-Special-Files.html */
int mknod (const char *filename, mode_t mode, dev_t dev) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Temporary-Files.html */
FILE * tmpfile (void) { }
FILE * tmpfile64 (void) { }
char * tmpnam (char *result) { }
char * tmpnam_r (char *result) { }
char * tempnam (const char *dir, const char *prefix) { }
char * mktemp (char *template) { }
int mkstemp (char *template) { }
char * mkdtemp (char *template) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Executing-a-File.html */
/* Need: We need this because exec kills all global variables, o we need to dump our tables before continuing */
int execv (const char *filename, char *const argv[]) {
    void* pre_call = ({
        if (prov_log_is_enabled()) {
            char* path = NULL;
            path = normalize_path(path, AT_FDCWD, filename);
            prov_log_record(make_op(Execute, path, null_fd, null_mode));
            prov_log_save();
        } else {
            prov_log_save();
        }
    });
}
int execl (const char *filename, const char *arg0, ...) {
        void* pre_call = ({
        if (prov_log_is_enabled()) {
            char* path = NULL;
            path = normalize_path(path, AT_FDCWD, filename);
            prov_log_record(make_op(Execute, path, null_fd, null_mode));
            prov_log_save();
        } else {
            prov_log_save();
        }
    });
    size_t varargs_size = ({
        /* Variadic: var args end with a sentinel NULL arg */
        size_t n_varargs = 0;
        while (n_varargs[arg0]) {
            ++n_varargs;
        }
        sizeof(char*) + (n_varargs + 1) * sizeof(char*);
    });
}
int execve (const char *filename, char *const argv[], char *const env[]) {
    void* pre_call = ({
        if (prov_log_is_enabled()) {
            char* path = NULL;
            path = normalize_path(path, AT_FDCWD, filename);
            prov_log_record(make_op(Execute, path, null_fd, null_mode));
            prov_log_save();
        } else {
            prov_log_save();
        }
    });
}
int fexecve (int fd, char *const argv[], char *const env[]) {
    void* pre_call = ({
        if (prov_log_is_enabled()) {
            prov_log_record(make_op(Execute, null_path, fd, null_mode));
            prov_log_save();
        } else {
            prov_log_save();
        }
    });
}
int execle (const char *filename, const char *arg0, ...) {
    void* pre_call = ({
        if (prov_log_is_enabled()) {
            char* path = NULL;
            path = normalize_path(path, AT_FDCWD, filename);
            prov_log_record(make_op(Execute, path, null_fd, null_mode));
            prov_log_save();
        } else {
            prov_log_save();
        }
    });
    size_t varargs_size = ({
        /* Variadic: var args end with a sentinel NULL arg + 1 final char *const env[] */
        size_t n_varargs = 0;
        while (n_varargs[arg0]) {
            ++n_varargs;
        }
        sizeof(char*) + (n_varargs + 1) * sizeof(char*);
    });
}
int execvp (const char *filename, char *const argv[]) {
    void* pre_call = ({
        if (prov_log_is_enabled()) {
            char* path = NULL;
            bool bin_exists = lookup_on_path(path, filename);
            if (bin_exists) {
                prov_log_record(make_op(Execute, path, null_fd, null_mode));
                prov_log_save();
            }
        } else {
            prov_log_save();
        }
    });
}
int execlp (const char *filename, const char *arg0, ...) {
    size_t varargs_size = ({
        size_t n_varargs = 0;
        while (n_varargs[arg0]) {
            ++n_varargs;
        }
        sizeof(char*) + (n_varargs + 1) * sizeof(char*);
    });
    void* pre_call = ({
        if (prov_log_is_enabled()) {
            char* path = NULL;
            bool bin_exists = lookup_on_path(path, filename);
            if (bin_exists) {
                prov_log_record(make_op(Execute, path, null_fd, null_mode));
                prov_log_save();
            }
        } else {
            prov_log_save();
        }
    });
}
/* Variadic: var args end with a sentinel NULL arg */

/* Docs: https://linux.die.net/man/3/execvpe1 */
int execvpe(const char *file, char *const argv[], char *const envp[]) {
    void* pre_call = ({
        if (prov_log_is_enabled()) {
            char* path = NULL;
            bool bin_exists = lookup_on_path(path, argv[0]);
            if (bin_exists) {
                prov_log_record(make_op(Execute, path, null_fd, null_mode));
                prov_log_save();
            }
        } else {
            prov_log_save();
        }
    });
}

/* Need: Fork does copy-on-write, so we want to deduplicate our structures first */
/* Docs: https://www.gnu.org/software/libc/manual/html_node/Creating-a-Process.html */
pid_t fork (void) { }
pid_t _Fork (void) { }
pid_t vfork (void) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/Process-Completion.html */
pid_t waitpid (pid_t pid, int *status_ptr, int options) { }
pid_t wait (int *status_ptr) { }
pid_t wait4 (pid_t pid, int *status_ptr, int options, struct rusage *usage) { }

/* Docs: https://www.gnu.org/software/libc/manual/html_node/BSD-Wait-Functions.html */
pid_t wait3 (int *status_ptr, int options, struct rusage *usage) { }

void exit (int status) {
    void* pre_call = ({
        prov_log_save();
        prov_log_disable();
    });
    void* post_call = ({
        __builtin_unreachable();
    });
}