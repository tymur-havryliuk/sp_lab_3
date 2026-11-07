#include <stdio.h>

// Рекурсія та цикл
int fact_rec(int n) {
    if (n <= 1)
        return 1;
    return n * fact_rec(n - 1);
}

int fact_loop(int n) {
    int result = 1;
    for (int i = 2; i <= n; i++)
        result *= i;
    return result;
}

int main() {
    for (int n = 0; n <= 10; n++) {
        printf("%2d! = %7d  (цикл: %d)\n", n, fact_rec(n), fact_loop(n));
    }
    return 0;
}
