#include <stdio.h>

// Побітові складені присвоєння, sizeof, типи float/double
int count_bits(int x) {
    int count = 0;
    while (x) {
        count += x & 1;
        x >>= 1;
    }
    return count;
}

double average(int a[], int n) {
    double sum = 0;
    for (int i = 0; i < n; i++)
        sum += a[i];
    return sum / n;
}

int main() {
    int flags = 0;
    flags |= 1 << 0;            // вмикаємо біт 0
    flags |= 1 << 3;            // вмикаємо біт 3
    flags ^= 1 << 5;            // перемикаємо біт 5
    printf("flags = %d (0x%X), бітів: %d\n", flags, flags, count_bits(flags));
    flags &= ~(1 << 3);         // вимикаємо біт 3
    printf("після &= ~8: %d\n", flags);

    int v = 3;
    v <<= 4;                    // 48
    v >>= 2;                    // 12
    printf("v = %d\n", v);

    int data[] = {4, 8, 15, 16, 23, 42};
    int n = sizeof(data) / sizeof(data[0]);
    printf("sizeof(char)=%d, sizeof(int)=%d, sizeof(float)=%d, sizeof(double)=%d\n",
           sizeof(char), sizeof(int), sizeof(float), sizeof(double));
    printf("sizeof(data) = %d байт, елементів: %d\n", sizeof(data), n);
    printf("середнє = %.3f\n", average(data, n));

    char name[] = "PLY";
    printf("sizeof(\"%s\") = %d (з нульовим символом)\n", name, sizeof name);
    return 0;
}
