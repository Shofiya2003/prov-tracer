#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdlib.h>

extern char** environ;

int main (int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <file>\n", argv[0]);
        exit(1);
    }
    FILE* fptr = fopen(argv[1], "r");
    if (fptr == NULL) {
        fprintf (stderr, "Could not open\n");
        exit(1);
    }
    char* test = malloc(10);
    free(test);

    #define BUFFER_SIZE 1024
    char buffer [BUFFER_SIZE];
    size_t size;

    if ((size = fread(&buffer, 1, BUFFER_SIZE, fptr)) > 0) {
        fwrite(buffer, size, 1, stdout);
    }

    fclose(fptr);

    int ret = fork();
    if (ret == 0) {
        execlpe("env", "env", NULL, environ);
        perror("execlp");
    } else if (ret > 0) {
        int ret2 = waitpid(ret, NULL, 0);
        if (ret2 == -1) {
            perror("waitpid");
        }
    } else {
        perror("fork");
    }

    return 0;
}
