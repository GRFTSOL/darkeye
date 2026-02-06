#include <QApplication>
#include "MainWindow.h"
#include "MyCustomWidget.h"

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    //MainWindow window;
    ColorWheelSimple mycustomwidget;
    mycustomwidget.show();
    //window.show();
    return app.exec();
}
