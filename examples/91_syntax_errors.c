#include <stdio.h>

// Синтаксичні помилки: парсер відновлюється (правило statement : error SEMI)
// і знаходить кілька помилок за один прогін
int main() {
    int x = 10;
    x = 3 + * 4;
    int y = (x + 2;
    printf("%d\n", x) 
    y = y @ 2;
    return 0;
}
