#include <QApplication>

#include "MyCustomWidget.h"

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);

    ColorWheelSimple mycustomwidget;
    mycustomwidget.show();

    return app.exec();
}
