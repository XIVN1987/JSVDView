#! python3
import os
import re
import sys
import ctypes
import collections
import configparser

import PyQt5.sip
from PyQt5 import QtCore, QtGui, Qt, uic
from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog, QInputDialog, QLineEdit
from PyQt5.QtWidgets import QHeaderView, QTreeWidgetItem

from cmsis_svd.parser import SVDParser
import jlink


'''
class SVDView(QWidget):
    def __init__(self, parent=None):
        super(SVDView, self).__init__(parent)
        
        uic.loadUi('SVDView.ui', self)
'''
from SVDView_UI import Ui_SVDView
class SVDView(QWidget, Ui_SVDView):
    def __init__(self, parent=None):
        super(SVDView, self).__init__(parent)
        
        self.setupUi(self)

        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1,  50)
        self.tree.setColumnWidth(2,  90)
        self.tree.header().setSectionResizeMode(QHeaderView.Interactive)

        self.initSetting()
        
    def initSetting(self):
        if not os.path.exists('setting.ini'):
            open('setting.ini', 'w')
        
        self.conf = configparser.ConfigParser()
        self.conf.read('setting.ini', encoding='utf-8')
        
        if not self.conf.has_section('globals'):
            self.conf.add_section('globals')
            self.conf.set('globals', 'dllpath', '')
            self.conf.set('globals', 'svdpath', '[]')
        self.linDLL.setText(self.conf.get('globals', 'dllpath'))
        for path in eval(self.conf.get('globals', 'svdpath')): self.cmbSVD.insertItem(10, path)
    
    @QtCore.pyqtSlot()
    def on_btnDLL_clicked(self):
        path, filter = QFileDialog.getOpenFileName(caption=u'JLinkARM.dll路径', filter=u'动态链接库文件 (*.dll)', directory=self.linDLL.text())
        if path != '':
            self.linDLL.setText(path)
    
    @QtCore.pyqtSlot()
    def on_btnSVD_clicked(self):
        path, filter = QFileDialog.getOpenFileName(caption=u'SVD文件路径', filter=u'SVD File (*.svd *.xml)', directory=self.cmbSVD.currentText())
        if path != '':
            self.cmbSVD.insertItem(0, path)
            self.cmbSVD.setCurrentIndex(0)

    @QtCore.pyqtSlot(str)
    def on_cmbSVD_currentIndexChanged(self, path):
        if not os.path.exists(path): return
        
        self.device = SVDParser.for_xml_file(path).get_device()
        
        self.cmbPeriph.clear()
        self.cmbPeriph.addItems(sorted([periph.name for periph in self.device.peripherals]))

    @QtCore.pyqtSlot(str)
    def on_cmbPeriph_currentIndexChanged(self, name):
        if not name: return

        self.periph = self.get_peripheral(name)

        self.linPeriph.setText(' @ 0x%08X' %self.periph._base_address)

        if self.periph.derived_from: periph = self.periph.get_derived_from()
        else:                        periph = self.periph

        self.tree.clear()
        for reg in periph.registers:
            Reg = QTreeWidgetItem(self.tree, [reg.name, '%02X' %reg.address_offset, '00000000', reg.description])
            
            if reg.derived_from: reg = reg.get_derived_from()

            for field in reg.fields:
                Field = QTreeWidgetItem(Reg, [field.name, '%d' %field.bit_offset if field.bit_width == 1 else
                                                          '%d:%d' %(field.bit_offset, field.bit_offset + field.bit_width - 1), '00', field.description])

        self.on_btnRefresh_clicked()

    @QtCore.pyqtSlot()
    def on_btnRefresh_clicked(self):
        try:
            self.jlink = jlink.JLink(self.linDLL.text(), 'Cortex-M0')
            
            reg_buf = self.jlink.read_mem_U32(self.periph._base_address, (self.periph.registers[-1].address_offset + 4) // 4)
        except Exception as e:
            print(e)
        else:
            for i in range(self.tree.topLevelItemCount()):
                Reg = self.tree.topLevelItem(i)

                value = reg_buf[int(Reg.text(1), 16) // 4]

                Reg.setText(2, '%08X' %value)

                for j in range(Reg.childCount()):
                    Field = Reg.child(j)

                    offset, width, mask = self.get_field_info(Field.text(1))

                    Field.setText(2, '%u' %((value >> offset) & mask))

    @QtCore.pyqtSlot(QTreeWidgetItem, int)
    def on_tree_itemClicked(self, item, column):
        if column == 2:
            if item.parent() == None:   # why not self.tree
                s, ok = QInputDialog.getText(self, 'Set Register Value', 'HEX Value:', QLineEdit.Normal, item.text(2))
                if ok:
                    try:
                        val = int(s, 16)
                        addr = self.periph._base_address + int(item.text(1), 16)
                        self.jlink.write_U32(addr, val)

                        self.on_btnRefresh_clicked()

                    except Exception as e:
                        print(e)
            else:
                offset, width, mask = self.get_field_info(item.text(1))

                i, ok = QInputDialog.getInt(self, 'Set Field Value', 'DEC Value:', int(item.text(2)), 0, mask, 1)
                if ok:
                    try:
                        addr = self.periph._base_address + int(item.parent().text(1), 16)
                        val = (self.jlink.read_U32(addr) & (~(mask << offset))) | (i << offset)
                        self.jlink.write_U32(addr, val)

                        self.on_btnRefresh_clicked()

                    except Exception as e:
                        print(e)

    def get_peripheral(self, name):
        for peripheral in self.device.peripherals:
            if peripheral.name == name:
                return peripheral

    def get_register(self, peripheral, name):
        for register in peripheral.registers:
            if register.name == name:
                return register

    def get_field(self, register, name):
        for field in register.fields:
            if field.name == name:
                return field

    def get_field_info(self, text):
        if ':' in text:
            start, end = text.split(':')
            offset, width = int(start), int(end) - int(start) + 1
            mask = (1 << width) - 1

            return (offset, width, mask)
        else:
            offset = int(text)

            return (offset, 1, 1)


    def closeEvent(self, evt):
        self.closed = True
        
        self.conf.set('globals', 'dllpath', self.linDLL.text())
        
        svdpaths = [self.cmbSVD.itemText(i) for i in range(self.cmbSVD.count())]
        if self.cmbSVD.currentIndex() not in [0, -1]: svdpaths = [self.cmbSVD.currentText()] + svdpaths     # 将当前项置于最前
        svdpaths = list(collections.OrderedDict.fromkeys(svdpaths))                                         # 保留顺序去重
        self.conf.set('globals', 'svdpath', repr(svdpaths[:10]))

        self.conf.write(open('setting.ini', 'w'))
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    svd = SVDView()
    svd.show()
    app.exec_()
