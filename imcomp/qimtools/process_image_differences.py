from qimview.utils.qt_imports import QtWidgets, QtCore, QtGui
from qimview.utils.utils import get_time

from qimview.image_readers import gb_image_reader

import cv2
import numpy as np


# Numeric item to allow better sorting of cells
class NumericItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other):
        return self.data(QtCore.Qt.UserRole) < other.data(QtCore.Qt.UserRole)


class ProcessImageDifferences(QtCore.QThread):
    # This is the signal that will be emitted during the processing.
    # By including int as an argument, it lets the signal know to expect
    # an integer argument when emitting.
    updateProgress = QtCore.Signal(int)

    def __init__(self, tw, statusBar, setProgress):
        QtCore.QThread.__init__(self)
        self.column = -1
        self.time_start = get_time()
        # Table Window to update
        self.tw = tw
        self.statusBar = statusBar
        self.setProgress = setProgress

    def __del__(self):
        self.wait()

    def run(self):
        print("ProcessDifferences run")
        # Is the display on the statusBar crashing sometimes ?
        # self.tw.statusBar().showMessage(" Processing image differences")
        # Compute image differences: more heavy processing
        self.time_start = get_time()
        inputs = dict()
        col = -1
        horizontal_header = self.tw.horizontalHeader()
        column_count = horizontal_header.count()
        for c in range(column_count):
            column_name = self.tw.horizontalHeaderItem(c).text()
            if column_name == 'diff':
                col = c
                break
        if col == -1:
            col = 1
            print("diff column not found, using column 1")
        # First get list of row ids before the user gets time to reorder the table
        self.tw.hideColumn(col)
        row_ids = []
        num_rows = self.tw.rowCount()
        # we could also use len(self.tw.all_data) but it works only for json files, not jpg
        for row in range(num_rows):
            # This is simply to show the bar
            row_item = NumericItem('')
            self.tw.setItem(row, col, row_item)
            row_id = self.tw.item(row, 0).text()
            row_ids.append([row, row_id, row_item])
        print("row_ids = {0}", row_ids)

        for row_info in row_ids:
            row = row_info[0]
            row_id = row_info[1]
            row_item = row_info[2]
            # This is simply to show the bar
            self.updateProgress.emit(row * 100 / num_rows)
            print(f"self.tw image1 {self.tw.image1} image2 {self.tw.image2}")
            print(f"{row_id} {self.tw.useful_data[row_id].keys()}")
            for im_type in ['out_set0','out_set1']:
                cv2_im = gb_image_reader.read(self.tw.useful_data[row_id][im_type])
                width = cv2_im.data.shape[1]
                height = cv2_im.data.shape[0]
                new_width = int(1000)
                new_height = int(new_width * height / width)
                to_np_resized = cv2.resize(cv2_im.data, (new_width, new_height), interpolation=cv2.INTER_AREA)
                inputs[im_type] = to_np_resized

            im1 = inputs['out_set0']
            im2 = inputs['out_set1']
            diff = cv2.mean(cv2.absdiff(im1, im2))
            # print "diff = ", diff, " ", type(diff)
            diff = np.mean(np.array(diff))
            # print "diff = ", diff, " ", type(diff)
            # if cells are reordered, the cell position is not valid anymore
            self.tw.write_number_item(row_item, col, diff)
        self.tw.showColumn(col)

        self.column = col
