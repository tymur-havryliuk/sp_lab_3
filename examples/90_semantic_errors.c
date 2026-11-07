#include <stdio.h>

// Синтаксично правильна програма з СЕМАНТИЧНИМИ помилками
int square(int x) {
    return x * x;
}

void hello() {
    return 5;               // void-функція повертає значення
}

int main() {
    int a = 5;
    int a = 6;              // повторне оголошення
    float f = 2.5;
    b = 10;                 // неоголошена змінна
    square(1, 2);           // неправильна кількість аргументів
    int r = f % 2;          // % для float
    10 = a;                 // присвоєння не-lvalue
    a[0] = 1;               // a — не масив
    undefined_func(a);      // неоголошена функція
    break;                  // break поза циклом
    int n = hello();        // void у виразі
    printf("%d %d\n", a);   // попередження: мало аргументів
    return 0;
}
