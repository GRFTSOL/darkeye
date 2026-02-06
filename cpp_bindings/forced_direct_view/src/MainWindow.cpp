#include "MainWindow.h"
#include <QLabel>
#include <QPushButton>
#include <QLineEdit>
#include <QVBoxLayout>
#include <QWidget>
#include <QLabel>
#include <Eigen/Dense>
#include <Eigen/Core>
#include <iostream>
#include <QDebug>
#include <sstream> // 用于将 Eigen 对象转为字符串
#include "MyCustomWidget.h"

using Eigen::MatrixXd;

MainWindow::MainWindow(QWidget *parent):QMainWindow(parent)
{
    setWindowTitle(tr("ForceView"));
    resize(480, 320);

    MatrixXd m(2, 2);
    m(0, 0) = 3;
    m(1, 0) = 2.5;
    m(0, 1) = -1;
    m(1, 1) = m(1, 0) + m(0, 1);
    std::cout << m << std::endl;


    initUI();
}

void MainWindow::initUI()
{
    QWidget *central = new QWidget(this);
    setCentralWidget(central);

    QVBoxLayout *layout = new QVBoxLayout(central);
    layout->addWidget(new QLabel(tr("ForceView — Qt 6 Widgets"), this));
    layout->addWidget(new QLineEdit(this));
    layout->addWidget(new QLabel("测试", this));
    layout->addWidget(new QPushButton(tr("OK"), this));

}

MainWindow::~MainWindow() = default;
