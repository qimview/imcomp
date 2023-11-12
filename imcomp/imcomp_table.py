
from qimview.utils.qt_imports import QtWidgets, QtCore, QtGui
from qimview.utils.utils import get_time
from imcomp import fill_table_data
import numpy as np
from collections import OrderedDict
from imcomp.qimtools.process_image_differences import ProcessImageDifferences
import os
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from qimview.image_viewers import MultiView

# Deal with compatibility issues of different Qt versions
if hasattr(QtCore.Qt, 'Vertical'):
    QT_ORIENTATION = QtCore.Qt
else:
    QT_ORIENTATION = QtCore.Qt.Orientation


def is_float_number(s):
    """ Returns True is string is a number. """
    try:
        float(s)
        return True
    except ValueError:
        return False


def is_int_number(s):
    """ Returns True is string is a number. """
    try:
        int(s)
        return True
    except ValueError:
        return False

# Numeric item to allow better sorting of cells
class NumericItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other):
        return self.data(QtCore.Qt.UserRole) < other.data(QtCore.Qt.UserRole)


class ImCompTable(QtWidgets.QTableWidget):
    def __init__(self, parent, _rows=0, _columns=0):
        super().__init__( _rows, _columns, parent)

        # store information about column sorting: order and number of current sorted column
        self.header_sort = dict()

        self.previous_row = 0

        # Compute value range (min,max) for each column
        self.column_range = dict()
        self.background_opacity = 90

        # export report
        self.default_report_file = 'report.json'

        # Logs
        self.verbosity = 0
        self.verbosity_LIGHT = 1
        self.verbosity_TIMING = 1 << 2
        self.verbosity_TIMING_DETAILED = 1 << 3
        self.verbosity_TRACE = 1 << 4
        self.verbosity_DEBUG = 1 << 5


    def create(self):

        vheader = QtWidgets.QHeaderView(QT_ORIENTATION.Vertical)
        # vheader.setResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.setVerticalHeader(vheader)
        hheader = QtWidgets.QHeaderView(QT_ORIENTATION.Horizontal)
        try:
            hheader.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            hheader.setSectionsMovable(True)
        except Exception as e:
            print("Qt hheader setting failed, old qt version ? {}".format(e))
        self.setHorizontalHeader(hheader)
        # self.cellClicked.connect(self.cell_was_clicked)
        self.currentCellChanged.connect(self.current_cell_changed)
        self.itemSelectionChanged.connect(self.item_selection_changed)

    def set_info(self, image_list, useful_data, multiview):
        self.image_list   = image_list
        self.useful_data  = useful_data
        self.multiview    : MultiView = multiview

    def print_log(self, mess):
        if self.verbosity & self.verbosity_LIGHT:
            print(mess)

    def set_verbosity(self, flag, enable=True):
        """
        :param v: verbosity flags
        :param b: boolean to enable or disable flag
        :return:
        """
        if enable:
            self.verbosity = self.verbosity | flag
        else:
            self.verbosity = self.verbosity & ~flag

    def check_verbosity(self, flag):
        return self.verbosity & flag

    def show_timing(self):
        return self.check_verbosity(self.verbosity_TIMING) or self.check_verbosity(self.verbosity_TIMING_DETAILED)

    def show_timing_detailed(self):
        return self.check_verbosity(self.verbosity_TIMING_DETAILED)

    def show_trace(self):
        return self.check_verbosity(self.verbosity_TRACE)

    def current_cell_changed(self, _row: int, _column: int, _prev_row, _prev_column) -> None:
        # we need 
        #   - image_list
        #   - useful_data
        #   - multiview
        #   
        """_summary_

        Args:
            _row (int): current cell row
            _column (int): current cell column
            _prev_row (_type_): previous cell row
            _prev_column (_type_): previous cell column
        """
        print(f"current_cell_changed {_row}")
        cell_changed_start = get_time()
        # print "current_cell_changed {0} {1}".format(_row, _column)
        # TODO: get column name
        column_title = self.horizontalHeaderItem(_column).text()

        if _row != self.previous_row:
            _font = QtGui.QFont()
            _font.setBold(False)
            if self.item(self.previous_row, 0):
                _font.setBold(False)
                self.item(self.previous_row, 0).setFont(_font)
            if self.item(_row, 0):
                self.previous_row = _row
                _font.setBold(True)
                self.item(self.previous_row, 0).setFont(_font)

        _row_id = self.item(_row, 0).text()
        self._row_id = _row_id

    def item_selection_changed(self) -> None:
        try:
            print('item_selection_changed')
            selected_ranges = self.selectedRanges()
            print(f'selected_ranges {selected_ranges}')
            image_dict = {}
            # number of selected rows
            total_selected = 0
            for _range in selected_ranges:
                total_selected +=  _range.bottomRow()-_range.topRow()+1
            print(f"total_selected {total_selected}")
            idx = 0
            for _range in selected_ranges:
                print(f" range rows {_range.topRow()} {_range.bottomRow()}")
                for _row in range(_range.topRow(), _range.bottomRow()+1):
                    _row_id = self.item(_row, 0).text()
                    for im in self.image_list:
                        # TODO: improve this part, for the moment, if only 1 row is selected,
                        # maintain previous names
                        if im != 'none':
                            key_str = f"{im}_{idx}" if total_selected > 1 else f"{im}"
                            image_dict[key_str] = self.useful_data[_row_id][im]
                    idx += 1
            print(f"image_dict {image_dict}")
            self.multiview.set_images(image_dict)
            nb_inputs = len(image_dict)
            max_viewers = 100
            print(f"self.image_list {self.image_list}")
            row_size = len([ l for l in self.image_list if l != 'none'])
            if nb_inputs>=1 and nb_inputs<=max_viewers:
                if total_selected>1 or self.multiview.nb_viewers_used > nb_inputs:
                    self.multiview.set_number_of_viewers(nb_inputs, max_columns=row_size)
                self.multiview.set_viewer_images()
                self.multiview.viewer_grid_layout.update()
                # self.multiview.update_image()
                # self.multiview.setFocus()
            self.multiview.update_image()
        except Exception as e:
            print(f"{e}")

    def read_report(self, data, statusBar, setProgress):
        # fill table with data
        nb_rows = self.rowCount()
        self.setUpdatesEnabled(False)
        for _row in range(nb_rows):
            self.hideRow(_row)
            setProgress(_row*100/nb_rows)
            QtCore.QCoreApplication.instance().processEvents()
            try:
                _row_id = self.item(_row, 0).text()
                if _row_id in data:
                    data_row = data[_row_id]
                    for column_name in self.column_list:
                        if column_name in data[_row_id]:
                            # TODO: get column position in the table
                            _col = self.column_list[column_name]['default_pos']
                            item = self.item(_row, _col)
                            if item:
                                # only fill empty cells?
                                if item.text() == '':
                                    item.setText(data_row[column_name])
                            else:
                                if is_int_number(data_row[column_name]):
                                    self.write_number_int(_row, _col, int(
                                        data_row[column_name]), True)
                                else:
                                    if is_float_number(data[_row_id][column_name]):
                                        self.write_number(_row, _col, float(
                                            data_row[column_name]), True)
                                    else:
                                        _item = QtWidgets.QTableWidgetItem(
                                            data_row[column_name])
                                        self.setItem(
                                            _row, _col, _item)
            except Exception as e:
                print("Error in setting row contents ", e)
            self.showRow(_row)
        setProgress(0)
        self.update_colors(statusBar, setProgress)
        self.setUpdatesEnabled(True)

    def write_file(self, params=None, selected_rows=None, save_folder=None):
        contents = dict()
        if params is not None:
            contents['params'] = params
        if selected_rows is None:
            selected_rows = np.arange(self.rowCount())
        for _row in selected_rows:
            try:
                _row_id = self.item(_row, 0).text()
                print(_row_id)
                contents[_row_id] = dict()
                horizontal_header = self.horizontalHeader()
                for _col in range(horizontal_header.count()):
                    column_name = self.horizontalHeaderItem(
                        _col).text()
                    if column_name != 'Unique Name':
                        if self.item(_row, _col):
                            contents[_row_id][column_name] = self.item(
                                _row, _col).text()
            except Exception as e:
                print("Error in extracting row contents ", e)

        print("save_folder = ", save_folder)
        print(self.default_report_file)
        if save_folder is None:
            fname = QtWidgets.QFileDialog.getSaveFileName(self, 'Save contents in file',
                                                          os.path.join(os.getcwd(), self.default_report_file), 'Json (*.json)')
        else:
            fname = [os.path.join(
                save_folder, os.path.basename(self.default_report_file))]
            # Replace directories in the params
            contents['params']['directory_list'] = ""
            for idx, image_set in enumerate(self.params['image_sets']):
                print(idx, " ", image_set)
                contents['params']['image_sets'][idx]['directory'] = os.path.join(
                    save_folder, self.image_list[idx + 1])
                if idx > 0:
                    contents['params']['directory_list'] += ','
                contents['params']['directory_list'] += os.path.join(
                    save_folder, self.image_list[idx + 1])

        print("fname = ", fname)
        # strange new issue?
        if fname[0].startswith("//?/"):
            print("filename may be too long for Windows !!!")
            fname_new = fname[0][4:]
        else:
            fname_new = fname[0]
        print("fname_new = ", fname_new)
        if os.path.isfile(fname_new):
            if os.path.isfile(fname_new+'.bak'):
                os.remove(fname_new+'.bak')
            os.rename(fname_new, fname_new+'.bak')
        fill_table_data.writeJson(OrderedDict(contents), fname_new)

    def export_to_excel(self):
        default_output = os.path.join(
            os.getcwd(), os.path.splitext(self.default_report_file)[0]+'.xls')
        filename = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save as excel file', default_output, ".xls(*.xls)")
        import importlib.util
        xlwt_spec = importlib.util.find_spec("xlwt")
        if xlwt_spec is None:
            print("Failed to load module xlwt, cannot export to excel file")
            return
        import xlwt
        wbk = xlwt.Workbook()
        self.sheet = wbk.add_sheet("sheet", cell_overwrite_ok=True)

        for column in range(self.columnCount()):
            header = self.horizontalHeaderItem(column)
            if header is not None:
                self.sheet.write(0, column, header.text())

            start_row = 1
            for col in range(self.columnCount()):
                for row in range(self.rowCount()):
                    try:
                        text = str(self.item(row, col).text())
                        try:
                            number = float(text)
                            self.sheet.write(start_row + row, col, number)
                        except Exception as e:
                            self.sheet.write(start_row + row, col, text)
                    except AttributeError as e:
                        pass
                        # print(" Failed to read data at ({},{}): {}".format(row, col, e))
            wbk.save(filename[0])

    def write_number(self, _row, _col, _val, can_edit=False, float_format='%.5f'):
        '''
        Write the number in the specified cell and update column range of values
        :param _row:
        :param _col:
        :param _val:
        :param can_edit:
        :param float_format:
        :return:
        '''
        _item = NumericItem(float_format % _val)
        _item.setData(QtCore.Qt.UserRole, _val)
        #_item = QtWidgets.QTableWidgetItem('%.4f' % _val)
        _item.setTextAlignment(QtCore.Qt.AlignRight)
        if not can_edit:
            # don't allow edit
            _item.setFlags(QtCore.Qt.ItemIsSelectable |
                            QtCore.Qt.ItemIsEnabled)

        self.setItem(_row, _col, _item)
        if 'min' not in self.column_range[_col]:
            self.column_range[_col]['min'] = _val
            self.column_range[_col]['max'] = _val
        else:
            self.column_range[_col]['min'] = min(
                self.column_range[_col]['min'], _val)
            self.column_range[_col]['max'] = max(
                self.column_range[_col]['max'], _val)

    def write_number_int(self, _row, _col, _val, can_edit=False):
        '''
        Write the number in the specified cell and update column range of values
        :param _row:
        :param _col:
        :param _val:
        :param can_edit:
        :return:
        '''
        _item = NumericItem('%d' % _val)
        _item.setData(QtCore.Qt.UserRole, _val)
        #_item = QtWidgets.QTableWidgetItem('%d' % _val)
        _item.setTextAlignment(QtCore.Qt.AlignRight)
        if not can_edit:
            # don't allow edit
            _item.setFlags(QtCore.Qt.ItemIsSelectable |
                            QtCore.Qt.ItemIsEnabled)

        self.setItem(_row, _col, _item)
        if 'min' not in self.column_range[_col]:
            self.column_range[_col]['min'] = _val
            self.column_range[_col]['max'] = _val
        else:
            self.column_range[_col]['min'] = min(
                self.column_range[_col]['min'], _val)
            self.column_range[_col]['max'] = max(
                self.column_range[_col]['max'], _val)

    def write_number_item(self, item, _col, _val, can_edit=False):
        '''
        Write the number in the specified cell and update column range of values
        :param item:
        :param _col:
        :param _val:
        :param can_edit:
        :return:
        '''
        item.setText('%.4f' % _val)
        item.setData(QtCore.Qt.UserRole, _val)
        item.setTextAlignment(QtCore.Qt.AlignRight)
        if not can_edit:
            # don't allow edit
            item.setFlags(QtCore.Qt.ItemIsSelectable |
                            QtCore.Qt.ItemIsEnabled)

        if 'min' not in self.column_range[_col]:
            self.column_range[_col]['min'] = _val
            self.column_range[_col]['max'] = _val
        else:
            self.column_range[_col]['min'] = min(
                self.column_range[_col]['min'], _val)
            self.column_range[_col]['max'] = max(
                self.column_range[_col]['max'], _val)

    def compute_image_differences_thread(self, setProgress, statusBar):
        statusBar.showMessage(" Processing image differences")
        # Compute image differences: more heavy processing
        self.differences_worker = ProcessImageDifferences(self)
        self.differences_worker.updateProgress.connect(setProgress)
        self.differences_worker.start()
        self.differences_worker.finished.connect(self.compute_image_differences_end)

    def compute_image_differences_end(self):
        c = self.differences_worker.column
        # update column colors
        try:
            if 'min' in self.column_range[c]:
                min_val = self.column_range[c]['min']
                max_val = self.column_range[c]['max']
                # print "min = ", min_val
                # print "max = ", max_val
                if min_val != max_val:
                    for r in range(self.rowCount()):
                        # set color for cell
                        # get value
                        val = float(self.item(r, c).text())
                        val = int((val-min_val)/(max_val-min_val)*256)
                        # print val
                        color = cm.jet(val)
                        # print color
                        self.item(r, c).setBackground(QtGui.QBrush(
                            QtGui.QColor(color[0]*255, color[1]*255, color[2]*255, self.background_opacity)))
        except Exception as e:
            print("Error in column range colors ", e)
        self.differences_worker.setProgress(0)
        self.differences_worker.statusBar.showMessage(" Image diff took: {0} sec".format(
            get_time()-self.differences_worker.time_start))

    def update_colors(self, statusBar, setProgress):
        """
        set column color for QTable
        """
        statusBar.showMessage(" Updating colors")
        nb_rows = self.rowCount()
        nb_columns = len(self.column_list)
        for c in range(nb_columns):
            setProgress(c*100/nb_columns)
            QtCore.QCoreApplication.instance().processEvents()
            self.setUpdatesEnabled(False)
            try:
                if 'min' in self.column_range[c]:
                    min_val = self.column_range[c]['min']
                    max_val = self.column_range[c]['max']
                    if min_val != max_val:
                        self.hideColumn(c)
                        for r in range(nb_rows):
                            # set color for cell
                            # get value
                            item = self.item(r, c)
                            if item:
                                if is_float_number(item.text()):
                                    val = float(item.text())
                                    val = int((val-min_val) / \
                                                (max_val-min_val)*256)
                                    # print val
                                    color = cm.jet(val)
                                    # print color
                                    item.setBackground(QtGui.QBrush(QtGui.QColor(color[0]*255, color[1]*255, color[2]*255,
                                                                                    self.background_opacity)))
                        self.showColumn(c)
            except Exception as e:
                print("Error in column range colors column {0} min {1} max {2}: ".format(
                    c, min_val, max_val), e)
                self.showColumn(c)
            self.setUpdatesEnabled(True)
        setProgress(0)

    def sort_header(self, column):
        if column in self.header_sort and self.header_sort[column] == QtCore.Qt.DescendingOrder:
                self.header_sort[column] = QtCore.Qt.AscendingOrder
        else:
            self.header_sort[column] = QtCore.Qt.DescendingOrder
        self.sortItems(column, self.header_sort[column])
        _font = QtGui.QFont()
        _font.setUnderline(False)
        _font.setItalic(False)
        _font.setBold(True)
        if 'current_column' in self.header_sort:
            self.horizontalHeaderItem(self.header_sort['current_column']).setFont(_font)

        self.header_sort['current_column'] = column
        _font.setUnderline(True)
        _font.setItalic(True)
        _font.setBold(True)
        self.horizontalHeaderItem(self.header_sort['current_column']).setFont(_font)

    def setColumnList(self, column_list):
        self.column_list = column_list
        for column_name in column_list:
            pos = self.column_list[column_name]['default_pos']
            item = QtWidgets.QTableWidgetItem(column_name)
            font = QtGui.QFont()
            font.setBold(True)
            item.setFont(font)
            item.setSizeHint( QtCore.QSize(self.column_list[column_name]['size_hint']*20, 60))
            self.setHorizontalHeaderItem(pos, item)
            # self.setColumnWidth(QtCore.QSize(self.column_list[col][1]*20, 60))
            if not self.column_list[column_name]['show']:
                self.hideColumn(pos)
        # click on header item
        self.hide()
        self.resizeColumnsToContents()
        self.show()
        self.horizontalHeader().setSectionsClickable(True)
        self.horizontalHeader().sectionClicked.connect(self.sort_header)
        # self.connect(self.horizontalHeader(), QtCore.SIGNAL('sectionClicked (int)'),
                                    # self.sort_header)

        #
        for c in range(len(column_list)):
            self.column_range[c] = dict()

