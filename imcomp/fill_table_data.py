
import os

# import ingest
import gzip
import json

from qimview.utils.qt_imports import QtWidgets, QtCore
import os


def writeJson(data, filename, compress = False, compressLevel = 9, indent=None):
	# Be sure to compress files that end with .gz
	if filename.endswith('.gz'):
		compress = True
	if compress:
		if filename.endswith('.json'):
			filename = filename + '.gz'
		with gzip.GzipFile(filename, 'w', compressLevel) as fileHandler:
			fileHandler.write(json.dumps(data, indent=indent).encode('utf-8'))
	else:
		with open(filename, 'w') as fileHandler:
			json.dump(data, fileHandler, indent=indent)


def readJson(filename):
	data = {}
	# Compressed json file
	if filename.endswith('.json.gz'):
		with gzip.GzipFile(filename, 'r') as fileHandler:
			data = json.loads(fileHandler.read().decode('utf-8'))
	# Classic json file
	else:
		with open(filename, 'r') as fileHandler:
			data = json.load(fileHandler)

	return data


def adapt_path(path):
	import sys
	is_windows = sys.platform.startswith('win')
	if os.path.isdir(path):
		# current path is a valid directory, return
		return path
	if is_windows:
		new_path = path.replace('/Public','P:')
	else:
		new_path = path.replace('P:','/Public')
	return new_path


def find_file(path, filename):
	if filename.startswith('out_'):
		filename = os.path.normpath(filename)
		filename = filename[filename.find(os.path.sep)+1:]
	filename_path = os.path.join(path, filename)
	if os.path.isfile(filename_path):
		return filename_path
	else:
		# look for basename within path
		# base_name = os.path.basename(filename)
		base_name = os.path.basename(filename.replace('\\',os.sep))
		for root, directories, filenames in os.walk(path):
			for file in filenames:
				if os.path.basename(file) == base_name:
					return os.path.join(root, file)
		print("Filename {0} not found within {1}".format(filename, path))
		return filename_path


def initTable(imcomp_win, config):
	title_string = ''
	default_report_file = '_report'
	image_sets = imcomp_win.get_params()['image_sets']
	image_list = [config['input']]
	# TODO: deal with different blendings!
	previous_basedir = ''

	# check if all image set have the same input directory
	if imcomp_win.get_params()['directory_list'] is not None:
		unique_directory = len(imcomp_win.get_params()['directory_list']) <= 1
	basedir0 = ''

	for per_set_output in config['outputs']:
		for idx, image_set in enumerate(image_sets):
			if 'name' in image_set:
				set_name = image_set['name']
				title_string += f' -- {set_name}'
				default_report_file += f'_{set_name}'
				image_list.append(f'{set_name}')
			else:
				suffix = image_set['suffix']
				basename_dir = os.path.basename(image_set['directory'])
				if idx == 0:
					basedir0 = basename_dir
				if basename_dir == previous_basedir:
					title_string += ' -- {0}'.format(suffix)
					default_report_file += '_{0}'.format(suffix)
				else:
					if idx > 0:
						commonprefix = os.path.commonprefix([basedir0, basename_dir])
						basename_dir = basename_dir[len(commonprefix):]
					title_string += ' -- {0}:{1}'.format(image_set['directory'], suffix)
					default_report_file += '_{0}_{1}'.format(basename_dir, suffix)
				if unique_directory:
					# use suffix name for set name
					set_suffix = suffix
				else:
					# use _set# for set name
					set_suffix = '_set{}'.format(idx)
				image_list.append('{0}{1}'.format(per_set_output, set_suffix))
				previous_basedir = basename_dir

	if 'diff' in config and len(config['diff'])>0:
		for pos, diff_pair in enumerate(config['diff']):
			if diff_pair[0] in image_list and diff_pair[1] in image_list:
				diff_name = '{}-{}'.format(diff_pair[0],diff_pair[1])
				image_list.append(diff_name)
				imcomp_win.setImageComparePair(diff_name, diff_pair[0], diff_pair[1])

	imcomp_win.setWindowTitle('Image Set Comparison '+title_string)
	imcomp_win.set_default_report_file(default_report_file+'.json')

	imcomp_win.set_image_list(image_list)
	imcomp_win.update_layout()

	imcomp_win.resize(3000, 1800)
	# print(image_list)
	return image_list


def CreateTableFromImages(imcomp_win, jpg_files, config):
	print("CreateTableFromImages")
	# find all the flare measure files
	useful_data = dict()
	all_data = dict()

	# [ [title, size hint, show] ]
	column_list = config['column_list_images']
	# print column_list

	# Create Qt table
	imcomp_win.create_table_widget(len(jpg_files), len(column_list))
	image_list = initTable(imcomp_win, config)
	imcomp_win.table_widget.setColumnList(column_list)
	imcomp_win.setAllData(all_data)
	image_sets = imcomp_win.get_params()['image_sets']
	imcomp_win.table_widget.setWordWrap (True)

	# Iterate over the data and write it out row by row.
	# TODO: code here is for 2 image sets generalize to any number of image sets
	row = 0
	for elt in jpg_files:
		col = column_list['Unique Name']['default_pos']
		unique_name = elt
		item = QtWidgets.QTableWidgetItem(unique_name)
		# Center alignment
		item.setTextAlignment(QtCore.Qt.AlignLeft)
		# don't allow edit
		item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
		# Add item
		imcomp_win.table_widget.setItem(row, col, item)

		# create a row_id using folder_name
		row_id = unique_name
		useful_data[row_id] = dict()

		# output file names
		# in the case of flare data, try to guess the original image
		if config['config_name'] == 'flare':
			for set_index in range(len(jpg_files[elt])):
				jpg_file = jpg_files[elt][set_index]
				original_stitched_filename = os.path.join(os.path.dirname(jpg_file),
														  os.path.basename(jpg_file))
				if not os.path.isfile(original_stitched_filename):
					print("original filename not found {0}".format(original_stitched_filename))
					suffix = image_sets[0]['suffix']
					# try without suffix
					original_stitched_filename = original_stitched_filename.replace(suffix, '')
					print("trying ", original_stitched_filename)
				if os.path.isfile(original_stitched_filename):
					break
			useful_data[row_id][config['input']] = original_stitched_filename
		else:
			useful_data[row_id][image_list[0]] = ""

		for n in range(len(image_sets)):
			useful_data[row_id][image_list[n+1]] = jpg_files[elt][n]

		row += 1

	imcomp_win.setUsefulData(useful_data)
	imcomp_win.set_table_info()
	imcomp_win.show()
	imcomp_win.raise_()
	imcomp_win.update_colors()
	imcomp_win.table_widget.resizeRowsToContents()
	return imcomp_win


def parse_images_from_dir(dir, name_filters, suffix, extensions=['.png', '.dxr', '.jpg'], recursive=True):
	'''
	List all jpgs containing filters (if any) in their filename and the specified suffix and name_filter
	:param dir:
	:param name_filters:
	:param suffix:
	:param extensions: list of accepted image extensions
	:return:
	'''
	filename_list1 = []
	filters = name_filters.split(',')
	# Find all mask in subdirectories
	for root, directories, filenames in os.walk(dir):
		for filename in filenames:
			extension_ok = False
			for ext in extensions:
				if filename.lower().endswith(ext):
					extension_ok = True
					break
			# filter on all substrings
			filter_ok = True
			jpg_filters = filters
			for f in jpg_filters:
				if f not in filename:
					filter_ok = False
					break
			if extension_ok and filter_ok:
				filename_list1.append(os.path.join(root, filename))
		if not recursive: break

	# Create list of common outputs
	list_stills = dict()
	for fn in filename_list1:
		full_path = os.path.dirname(fn)
		print(full_path)
		directory_name = os.path.relpath(full_path, dir)
		image_name = os.path.basename(os.path.splitext(fn)[0])
		if suffix != '':
			if image_name.endswith(suffix):
				image_name = image_name[:-len(suffix)]
			else:
				continue
		if directory_name != '':
			unique_name = directory_name.replace("/","_").replace('\\','_') + '_' + image_name
		else:
			unique_name = image_name
		list_stills[unique_name] = fn
	return list_stills


def parse_images(image_sets, name_filter, extensions, recursive=True):
	lists = []
	for image_set in image_sets:
		print("Parsing for {}".format(image_set['suffix']))
		list_stills = parse_images_from_dir(image_set['directory'], name_filter, image_set['suffix'],
											extensions=extensions, recursive=recursive)
		lists.append(list_stills)

	if len(lists) == 0:
		return None

	# merge lists
	list_files = dict()
	# initialize with the first list
	for s in lists[0]:
		still_ok = True
		for l in range(1, len(lists)):
			if s not in lists[l]:
				still_ok = False
				break
		if still_ok:
			list_files[s] = []
			for l in range(len(lists)):
				list_files[s].append(lists[l][s])

	return list_files

