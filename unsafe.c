#include <stdio.h>
#include <string.h>

int main() {
    char buffer[5];
    char input[100] = "This string is definitely longer than 5 characters";
    
    strcpy(buffer, input);
    
    printf("Buffer: %s\n", buffer);
    return 0;
}
