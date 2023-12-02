
from qimview.utils.qt_imports       import QtWidgets, QtCore, QtGui
from qimview.utils.viewer_image     import *
from qimview.utils.menu_selection   import MenuSelection
from qimview.image_viewers          import MultiView, ViewerType
from .imcomp_table                  import ImCompTable
from qimview.cache                  import FileCache
from qimview.image_readers          import gb_image_reader
import sys
from typing                         import Optional, Any, Dict
from .imcomp_config                 import ImCompConfig
# Only enable vlc player for windows by default

userconf = ImCompConfig.user_config()
try:
    use_vlc_player = userconf.get_boolean('VIDEOPLAYER','UseVLC')
    print(f"use_vlc_player {use_vlc_player}")
except Exception as e:
    print(f"Failed to get UseVLC config {e}")
    use_vlc_player = False # sys.platform == "win32"

if use_vlc_player:
    try:
        from qimview.video_player.vlc_player import VLCPlayer as VideoPlayer
        has_video_player = True
    except Exception as e:
        print(f"Failed to import VLCPlayer {e}")
        has_video_player = False
else:
    try:
        from qimview.video_player.video_player import VideoPlayer
        has_video_player = True
    except Exception as e:
        print(f"Failed to import video_player {e}")
        has_video_player = False

from imcomp import fill_table_data
import sys
import os
from shutil import copyfile
import copyreg
import multiprocessing
import types
import psutil
# import matplotlib
# from matplotlib import cm
# matplotlib.rcParams.update({'font.size': 22})


# Deal with compatibility issues of different Qt versions
if hasattr(QtCore.Qt, 'Vertical'):
    QT_ORIENTATION = QtCore.Qt
else:
    QT_ORIENTATION = QtCore.Qt.Orientation


def _pickle_method(m):
    if m.__self__ is None:
        return getattr, (m.__self__.__class__, m.__func__.__name__)
    else:
        return getattr, (m.__self__, m.__func__.__name__)

copyreg.pickle(types.MethodType, _pickle_method)


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

class ParallelImageRead:
    def __init__(self):
        pass

    def __call__(self, image_filename):
        try:
            cv2_im = gb_image_reader.read(image_filename)
        except Exception as e:
            print("Failed to load image {0}: {1}".format(image_filename, e))
            return None
        else:
            return cv2_im

    def process(self, image_list):
        pool = multiprocessing.Pool()
        return pool.map(self, image_list)

class EmptyIconProvider(QtWidgets.QFileIconProvider):
    def icon(self, _):
        return QtGui.QIcon()

class ImCompWindow(QtWidgets.QMainWindow):

    """
    Main class that controls the interface
    """
    def __init__(self, parent=None,
                    viewer_mode = ViewerType.QT_VIEWER):
        super(ImCompWindow, self).__init__(parent)

        self.main_widget = QtWidgets.QWidget(self)
        # no edits
        # self.table_widget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.create_menu()

        # Not maintained
        # # add figure widget on the right
        # # show current column value vs all sorted values
        # self.value_in_range_fig = Figure()
        # self.value_in_range_canvas = FigureCanvas(self.value_in_range_fig)
        # self.value_in_range_canvas.setMinimumSize(400, 100)

        self.menu_compute = self.menuBar().addMenu(self.tr('Compute'))
        start_bc = self.menu_compute.addAction(self.tr('Resulting image differences'))
        start_bc.triggered.connect(self.compute_image_differences)
        start_bc = self.menu_compute.addAction(self.tr('Update Colors'))
        start_bc.triggered.connect(self.update_colors)

        # self.statusBar()
        self.statusBar().setContentsMargins(2,2,2,2)

        self.progressBar = QtWidgets.QProgressBar()
        self.progressBar.setMaximumWidth(210)

        self.cache_progress_widget = QtWidgets.QWidget()
        self.cache_progress_widget.setMaximumWidth(200)
        self.cache_progress_widget.setMaximumHeight(50)
        self.cache_progress_layout = QtWidgets.QVBoxLayout()
        self.cache_progress_layout.setContentsMargins(2,2,2,2)
        self.cache_progress_widget.setLayout(self.cache_progress_layout)

        self.image_cache_progress = QtWidgets.QProgressBar()
        self.image_cache_progress.setMaximumHeight(25)
        self.image_cache_progress.setMaximumWidth(200)
        self.image_cache_progress.setTextVisible(False)
        self.file_cache_progress = QtWidgets.QProgressBar()
        self.file_cache_progress.setMaximumHeight(25)
        self.file_cache_progress.setMaximumWidth(200)
        self.file_cache_progress.setTextVisible(False)
        self.cache_progress_layout.addWidget(self.file_cache_progress)
        self.cache_progress_layout.addWidget(self.image_cache_progress)

        self.statusBar().addPermanentWidget(self.progressBar)
        self.statusBar().addPermanentWidget(self.cache_progress_widget)
        self.cache_progress_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.cache_progress_widget.customContextMenuRequested.connect(self.show_cache_progress_menu)

        # Create FileCache instance
        self.file_cache = FileCache()
        self.file_cache.set_memory_bar(self.file_cache_progress)
        # gb_image_reader.set_file_cache(self.file_cache)

        # Add popup menu to cache progress bar
        self._cache_progress_menu = QtWidgets.QMenu(self.image_cache_progress)

        self.action_file_cache_enabled = QtGui.QAction("File cache enabled", self._cache_progress_menu, checkable=True)
        self.action_file_cache_enabled.setChecked(True)
        self._cache_progress_menu.addAction(self.action_file_cache_enabled)
        self._cache_progress_menu.triggered.connect(self.toggle_file_cache)

        # set cache in percentage of memory
        cache_unit = 1024*1024 # 1 Mb
        total_memory = psutil.virtual_memory().total / cache_unit
        self._cache_sizes = {
                    f'2%:  {int(0.02*total_memory)} Mb' :int(0.02*total_memory), 
                    f'5%:  {int(0.05*total_memory)} Mb' :int(0.05*total_memory), 
                    f'10%: {int(0.10*total_memory)} Mb' :int(0.10*total_memory), 
                    f'20%: {int(0.20*total_memory)} Mb' :int(0.20*total_memory),
                    f'40%: {int(0.40*total_memory)} Mb' :int(0.40*total_memory)
        }
        self._default_file_cache_size = f'10%: {int(0.10*total_memory)} Mb'
        # self._cache_progress_menu.addSection("File Cache")
        self._file_cache_selection = MenuSelection("File Cache", self._cache_progress_menu,
                                        self._cache_sizes, self._default_file_cache_size,
                                        self.update_file_max_cache_size)
        self._cache_progress_menu.addSeparator()
        self.action_load_files_in_cache = self._cache_progress_menu.addAction('Load files in cache')
        self._cache_progress_menu.addSeparator()
        # self._cache_progress_menu.addSection("Image Cache")
        self._default_image_cache_size = f'20%: {int(0.20*total_memory)} Mb'
        self._image_cache_selection = MenuSelection("Image Cache", self._cache_progress_menu,
                                        self._cache_sizes, self._default_image_cache_size,
                                        self.update_image_max_cache_size)
        self.action_load_files_in_cache.triggered.connect(self.load_files_in_cache)

        # Enable or Disable file cache
        self.toggle_file_cache()

        self.params : Optional[Dict[str, Any]] = None
        self.viewer_mode = viewer_mode
        self.table_widget : Optional[ImCompTable] = None
        self.clip = QtWidgets.QApplication.clipboard()

        self.image1 = dict()
        self.image2 = dict()
        self.verbosity = 0
        self.verbosity_LIGHT = 1
        self.verbosity_TIMING = 1 << 2
        self.verbosity_TIMING_DETAILED = 1 << 3
        self.verbosity_TRACE = 1 << 4
        self.verbosity_DEBUG = 1 << 5
        # self.set_verbosity(self.verbosity_TIMING_DETAILED)
        # self.set_verbosity(self.verbosity_TRACE)

    def create_menu(self):
        self.option_menu = self.menuBar().addMenu(self.tr('File'))
        read_menu = self.option_menu.addAction(self.tr('Read file'))
        read_menu.triggered.connect(self.read_file)
        write_menu = self.option_menu.addAction(self.tr('Write file'))
        write_menu.triggered.connect(self.write_file)
        write_menu = self.option_menu.addAction(self.tr('Reload'))
        write_menu.triggered.connect(self.reload)
        start_sc = self.option_menu.addAction(self.tr('Export current image to clipboad'))
        start_sc.triggered.connect(self.export_to_clipboard)
        start_ex = self.option_menu.addAction(self.tr('Export to excel'))
        start_ex.triggered.connect(self.export_to_excel)

        self.option_menu = self.menuBar().addMenu(self.tr('Options'))
        self.option_readsize = self.option_menu.addMenu(self.tr('Read image size'))
        self.read_sizes = {'full':1, "1/2":2, "1/4":4, "1/8":8}
        self.read_size_selection = MenuSelection("Read size", self.option_readsize, self.read_sizes,
                                            _default='full', _callback=self.set_readsize)

        # self.antialiasing_menu = QtWidgets.QAction('anti-aliasing',  self.option_menu, checkable=True)
        # self.antialiasing_menu.setChecked(True)
        # self.anti_aliasing = True
        # self.option_menu.addAction(self.antialiasing_menu)
        # self.antialiasing_menu.triggered.connect(self.toggle_antialiasing)

        self.raw_bayer = {
            'Read': None,
            'Bayer0': ImageFormat.CH_GBRG,
            'Bayer1': ImageFormat.CH_BGGR,
            'Bayer2': ImageFormat.CH_RGGB,
            'Bayer3': ImageFormat.CH_GRBG
            }
        self.default_raw_bayer = 'Read'
        self.option_raw_bayer = self.option_menu.addMenu('RAW Bayer')
        for l in self.raw_bayer.keys():
            action = QtGui.QAction(l,  self.option_raw_bayer, checkable=True)
            self.option_raw_bayer.addAction(action)
            if l == self.default_raw_bayer:
                action.setChecked(True)
                self.current_raw_bayer = l
        self.option_raw_bayer.triggered.connect(self.update_raw_bayer_callback)

    def show_cache_progress_menu(self, pos):
        self._cache_progress_menu.show()
        self._cache_progress_menu.popup( self.image_cache_progress.mapToGlobal(pos) )

    def toggle_file_cache(self):
        is_enabled = self.action_file_cache_enabled.isChecked()
        self._file_cache_selection.setEnabled(is_enabled)
        self.action_load_files_in_cache.setEnabled(is_enabled)
        if is_enabled:
            gb_image_reader.set_file_cache(self.file_cache)
        else:
            gb_image_reader.set_file_cache(None)
            self.file_cache.reset()
            self.file_cache.check_size_limit()


    def update_file_max_cache_size(self):
        try:
            new_cache_size = self._file_cache_selection.get_selection_value()
            if gb_image_reader.file_cache is not None:
                gb_image_reader.file_cache.set_max_cache_size(new_cache_size)
            self.file_cache_progress.setToolTip(f"{new_cache_size} Mb")
        except Exception as e:
            print(f"Failed to set file cache size with exception {e}")

    def update_image_max_cache_size(self):
        try:
            new_cache_size = self._image_cache_selection.get_selection_value()
            self.multiview.cache.set_max_cache_size(new_cache_size)
            self.image_cache_progress.setToolTip(f"{new_cache_size} Mb")
        except Exception as e:
            print(f"Failed to set image cache size with exception {e}")

    def set_image_list(self, imlist):
        self.image_list = imlist

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

    def set_readsize(self):
        self.multiview.set_read_size(self.read_size_selection.get_selection())

    def update_raw_bayer_callback(self):
        # change bayer phase of current displayed image?
        menu = self.option_raw_bayer
        for action in menu.actions():
            if action.text() == self.current_raw_bayer:
                action.setChecked(False)
        for action in menu.actions():
            if action.isChecked():
                self.current_raw_bayer = self.multiview.current_raw_bayer = action.text()
        self.multiview.update_image()

    def create_table_widget(self, _rows=0, _columns=0):
        self.table_widget = ImCompTable(self, _rows=_rows, _columns=_columns)
        self.table_widget.create()

    def set_table_info(self):
        if self.table_widget:
            self.table_widget.set_info(self.image_list, self.useful_data, self.multiview)

    def set_params(self, params : Dict[str, Any]) -> None:
        self.params = params

    def get_params(self):
        return self.params

    def fill_data(self, config):
        if self.params:
            jpeg_only = self.params['config'] == 'default'
            list_jpegs = fill_table_data.parse_images(self.params['image_sets'], self.params['filters'],
                                                        self.params['ext'], self.params['recursive'])
            fill_table_data.CreateTableFromImages(self, list_jpegs, config)
            if self.params['report'] and self.table_widget:
                self.table_widget.read_report(self.params['report'], self.statusBar(), self.setProgress)

    def set_default_report_file(self, filename):
        print(" set_default_report_file {0}".format(filename))
        self.table_widget.default_report_file = filename

    def read_file(self):
        fname = QtWidgets.QFileDialog.getOpenFileName(None, 'Read contents from file',
                                                  self.default_report_file, 'Json (*.json)')
        self.read_report(fname[0])

    def reload(self):
        self.fill_data()

    def read_report(self, filename):
        import os
        self.statusBar().showMessage(" Reading report {0}".format(os.path.basename(filename)))
        data = fill_table_data.readJson(filename)
        self.table_widget.read_report(data, self.statusBar(), self.setProgress)

    def write_file(self, selected_rows=None, save_folder=None):
        self.table_widget.write_file(self.params, selected_rows, save_folder)

    def export_to_clipboard(self):
        self.multiview.set_clipboard(self.clip, save_image=True)
        self.multiview.update_image()
        self.multiview.set_clipboard(None,      save_image=False)

    def export_to_excel(self):
        self.table_widget.export_to_excel()

    def setUsefulData(self, useful_data):
        self.useful_data = useful_data

    def load_files_in_cache(self):
        # start reading in the cache file ?
        filename_list = []
        for row in self.useful_data:
            for im in self.image_list:
                if im != 'none':
                    filename_list.append(self.useful_data[row][im])
        print(f"ImCompWindow.load_files_in_cache() {len(filename_list)} files")
        self.file_cache.add_files(filename_list)

    def setAllData(self, all_data):
        self.all_data = all_data

    def setImageComparePair(self, diff_name, image1, image2):
        """
        :param diff_name: name that identifies the difference
        :param image1: Name of first image to compare in self.useful_data
        :param image2: Name of second image to compare in self.useful_data
        """
        self.image1[diff_name] = image1
        self.image2[diff_name] = image2

    def folder_select_changed(self, pos):
        current_text = self.folder_select.currentText()
        if current_text.lower() == "root":
            current_index = QtCore.QModelIndex()
        else:
            current_index = self.model.index(self.folder_select.currentText())
        self.filesystem_tree.setRootIndex(current_index)

    def set_next_row(self):

        selected_ranges = self.table_widget.selectedRanges()
        new_ranges = []
        # Get selected range and increase positions
        # not working well for the moment
        # if len(selected_ranges) == 1:
        #     _range = selected_ranges[0]
        #     left   = _range.leftColumn()
        #     right  = _range.rightColumn()
        #     top    = _range.topRow()
        #     bottom = _range.bottomRow()
        #     out_range = QtWidgets.QTableWidgetSelectionRange(top, left, top, right)
        #     in_range   = QtWidgets.QTableWidgetSelectionRange(bottom+1, left, bottom+1, right)
        #     # new_ranges.append(new_range)
        #     # self.table_widget.selectRow(self.table_widget.previous_row+1)
        #     self.table_widget.setRangeSelected(out_range, False)
        #     self.table_widget.setRangeSelected(in_range, True)
        # else:
        self.table_widget.selectRow(self.table_widget.previous_row+1)
        # Set focus to widget under cursor
        widget = QtWidgets.QApplication.instance().widgetAt(QtGui.QCursor.pos())
        if widget: widget.setFocus()

    def set_previous_row(self):
        self.table_widget.selectRow(max(0,self.table_widget.previous_row-1))
        # Set focus to widget under cursor
        widget = QtWidgets.QApplication.instance().widgetAt(QtGui.QCursor.pos())
        if widget: widget.setFocus()

    def update_layout(self):
        print("update_layout")

        # ----- Left widget -----
        self.left_tabs_widget = QtWidgets.QTabWidget()
        # --- Table tab
        self.left_tabs_widget.addTab(self.table_widget, 'table')

        # --- folder tab
        folder_tab_widget = QtWidgets.QWidget()
        vertical_layout = QtWidgets.QVBoxLayout()
        folder_tab_widget.setLayout(vertical_layout)

        # user paths
        user_path = os.path.expanduser('~')
        std_paths = [os.path.expanduser('~'), os.getcwd()]
        # picture path
        picture_path = os.path.join(user_path, "Pictures")
        if os.path.isdir(picture_path):
            std_paths.append(picture_path)

        # command line folders paths
        sets_folders = []
        for image_set in self.params['image_sets']:
            dir = image_set['directory']
            if dir not in sets_folders:
                sets_folders.append(dir)

        # --- root folder selection
        self.folder_select = QtWidgets.QComboBox()
        self.folder_select.setMaximumWidth(int(self.width()/3))
        self.folder_select.addItems(sets_folders)
        self.folder_select.addItems(std_paths)
        self.folder_select.addItem("Root")
        self.folder_select.currentIndexChanged.connect(self.folder_select_changed)
        vertical_layout.addWidget(self.folder_select)

        # --- filesystem tree view/model
        self.model = QtWidgets.QFileSystemModel()
        # Set user home directory as root
        #print(f"set model root path to {user_path}")
        self.model.setRootPath(user_path)
        # self.model.setFilters(QDir::Files | QDir::AllDirs | QDir::NoDotAndDotDot)
        # *.dxr DXO image format
        # *.ARW sony raw image format

        extension_list = gb_image_reader.extensions()
        extension_list.extend(['*.MP4'])
        full_list = []
        for e in extension_list:
            if e.lower() not in full_list:
                full_list.append(f'*{e}')
            if e.upper() not in full_list:
                full_list.append(f'*{e}')

        self.model.setNameFilters(full_list)
        self.model.setIconProvider(EmptyIconProvider())
        self.filesystem_tree = QtWidgets.QTreeView()
        self.filesystem_tree.setModel(self.model)
        self.filesystem_tree.setUniformRowHeights(True)

        print(f" root index is {self.filesystem_tree.rootIndex()}")
        self.filesystem_tree.setRootIndex(self.model.index(self.folder_select.currentText()))

        self.filesystem_tree.setAnimated(False)
        self.filesystem_tree.setIndentation(20)
        self.filesystem_tree.setSortingEnabled(True)
        self.filesystem_tree.setWindowTitle("Dir View")
        # self.filesystem_tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems)
        self.filesystem_tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.filesystem_tree.selectionModel().selectionChanged.connect( self.on_filesystem_selection_changed)

        vertical_layout.addWidget(self.filesystem_tree)

        self.left_tabs_widget.addTab(folder_tab_widget, 'File System')

        # ----- Right widget -----
        self.right_tabs_widget = QtWidgets.QTabWidget()

        # --- create multiview tab

        multiview_widget = QtWidgets.QWidget()
        multiview_layout = QtWidgets.QVBoxLayout()
        multiview_widget.setLayout(multiview_layout)

        # within parent widget and layout
        self.multiview = MultiView(parent=multiview_widget, viewer_mode=self.viewer_mode)
        self.multiview.set_key_down_callback(self.set_next_row)
        self.multiview.set_key_up_callback  (self.set_previous_row)
        self.multiview.set_cache_memory_bar(self.image_cache_progress)
        self.multiview.set_verbosity(self.verbosity)
        multiview_layout.addWidget(self.multiview, 1)

        self.multiview.set_message_callback( lambda m : self.statusBar().showMessage(m))

        images_dict = {}
        for im in self.image_list:
            images_dict[im] = None
        self.multiview.set_images(images_dict)
        self.multiview.update_layout()
        # self.multiview.show()
        self.right_tabs_widget.addTab(multiview_widget,  self.params['config_name'])

        # # --- create main tab
        # main_tab = QtWidgets.QWidget()
        # self.main_tab_widget = main_tab
        # self.right_tabs_widget.addTab(main_tab, self.params['config_name'])
        # main_tab.setLayout(vertical_layout)

        # --- create help tab
        help_tab = QtWidgets.QWidget()
        self.right_tabs_widget.setMovable(True)
        self.right_tabs_widget.addTab(help_tab, "Help")
        doc_layout = QtWidgets.QVBoxLayout()
        view = QtWidgets.QTextBrowser()
        # html has been generated from the webpage https://html-online.com/editor/
        file_dir = os.path.abspath(os.path.dirname(__file__))
        with open(os.path.join(file_dir,"help/imcomp_help.html")) as imcomp_help:
            view.setText(imcomp_help.read())
        view.show()
        view.raise_()
        doc_layout.addWidget(view)
        help_tab.setLayout(doc_layout)

        # --- create video tab
        if has_video_player:
            video_tab = QtWidgets.QWidget()
            self.right_tabs_widget.setMovable(True)
            self.right_tabs_widget.addTab(video_tab, "Video")
            video_layout = QtWidgets.QHBoxLayout()
            self.videoplayer1 = VideoPlayer(self)
            video_layout.addWidget(self.videoplayer1, 1)
            self.videoplayer2 = VideoPlayer(self)
            video_layout.addWidget(self.videoplayer2, 1)
            video_tab.setLayout(video_layout)

        # --- main layout
        main_layout = QtWidgets.QHBoxLayout()
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(self.left_tabs_widget)
        splitter.addWidget(self.right_tabs_widget)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        main_layout.addWidget(splitter)
        self.main_widget.setLayout(main_layout)
        self.setCentralWidget(self.main_widget)
        self.print_log("update_layout done")

    def on_filesystem_selection_changed(self, selected, deselected):
        #print("selectedIndexes ", self.filesystem_tree.selectedIndexes())
        selection_list = self.filesystem_tree.selectedIndexes()
        #print("selection_list size {}".format(len(selection_list)))
        file_list = []
        for index in selection_list:
            selected = index
            indexItem = self.model.index(selected.row(), 0, selected.parent())  # print(indexItem)
            filePath = self.model.filePath(indexItem)
            if filePath not in file_list:
                file_list.append(filePath)
        print(f"file_list {file_list}")
        self.on_selection(file_list)

    def on_selection(self, file_list):
        nb_selections = len(file_list)
        if has_video_player and nb_selections == 1 and file_list[0].lower().endswith("mp4"):
            self.videoplayer1.set_video(file_list[0])
            self.videoplayer1.set_synchronize(None)
            self.videoplayer2.hide()
        else:
            if has_video_player and nb_selections ==2 and file_list[0].lower().endswith("mp4") and file_list[1].lower().endswith("mp4"):
                self.videoplayer1.set_synchronize(self.videoplayer2)
                self.videoplayer2.set_synchronize(self.videoplayer1)
                self.videoplayer1.set_video(file_list[0])
                self.videoplayer2.set_video(file_list[1])
                self.videoplayer2.show()
            else:
                def get_name(path, maxlength=15):
                    return os.path.splitext(os.path.basename(path))[0][-maxlength:]

                images_dict = {}
                for idx, im in enumerate(file_list):
                    image_key = f'{idx}...{get_name(im)}'
                    images_dict[image_key] = im
                print(f" images_dict {images_dict}")
                self.multiview.set_images(images_dict)
                self.multiview.set_number_of_viewers(len(images_dict))
                self.multiview.set_viewer_images()
                # self.multiview.viewer_grid_layout.update()
                self.multiview.update_image()

    def handleNewWindow(self):
        window = QtWidgets.QMainWindow(self)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setWindowTitle(self.tr('New Window'))
        return window

    def get_array(self, data, key):
        if key in list(data.keys()):
            return np.array(data[key]['values'])
        else:
            print(" dictionary key {0} not found (keys are {1})".format(key, list(data.keys())))
            return None


    def keyPressEvent(self, event):
        if type(event) == QtGui.QKeyEvent:
            if self.show_trace():
                print("key is ", event.key())
                print("key down int is ", int(QtCore.Qt.Key_Down))
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            if event.key() == QtCore.Qt.Key_F11:
                print("key F11 pressed")
                # self.main_tab_widget.setWindowState(
                #     #self.main_tab_widget.windowState() ^
                #                                     QtCore.Qt.WindowFullScreen)
                self.setWindowState(self.windowState() ^ QtCore.Qt.WindowFullScreen)
                self.table_widget .setVisible(not self.table_widget .isVisible())
            # allow to switch between images by pressing Alt+'image position' (Alt+0, Alt+1, etc)
            if modifiers & QtCore.Qt.AltModifier:
                # select row down
                if event.key() == QtCore.Qt.Key_Plus:
                    print("event + {}".format(self.table_widget.previous_row))
                    # items = self.table_widget.selectedItems()
                    # _col = items[0].column()
                    self.table_widget.cellClicked.emit(self.table_widget.previous_row+2, 1)

                # select row up
                if event.key() == QtCore.Qt.Key_Minus:
                    print("event - {}".format(self.table_widget.previous_row))
                    # items = self.table_widget.selectedItems()
                    # _col = items[0].column()
                    self.table_widget.cellClicked.emit(max(0, self.table_widget.previous_row-1), 0)
                event.accept()
                return

            selected = self.table_widget.selectedRanges()
            if event.modifiers() & QtCore.Qt.ControlModifier:
                if event.key() == QtCore.Qt.Key_C:  # copy
                    s = '\t' + "\t".join([str(self.table_widget.horizontalHeaderItem(i).text()) for i in
                                          range(selected[0].leftColumn(), selected[0].rightColumn() + 1)])
                    s = s + '\n'

                    for r in range(selected[0].topRow(), selected[0].bottomRow() + 1):
                        # s += self.table_widget.verticalHeaderItem(r).text() + '\t'
                        for c in range(selected[0].leftColumn(), selected[0].rightColumn() + 1):
                            try:
                                s += str(self.table_widget.item(r, c).text()) + "\t"
                            except AttributeError:
                                s += "\t"
                        s = s[:-1] + "\n"  # eliminate last '\t'
                    self.clip.setText(s)

            # here accept the event and do something
            # deal with F1 key
            event.accept()
        else:
            event.ignore()

    def setProgress(self, progress):
        self.progressBar.setValue(progress)

    def compute_image_differences(self):
        self.table_widget.compute_image_differences_thread(self.setProgress, self.statusBar())

    def update_colors(self):
        """
        set column color for QTable
        """
        self.table_widget.update_colors(self.statusBar(), self.setProgress)

