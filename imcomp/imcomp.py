import os, sys
import argparse, logging
import json
from imcomp import version, fill_table_data
import glob

from qimview.utils.qt_imports   import QtWidgets, QtCore
from qimview.image_viewers      import ViewerType
from imcomp                     import ImCompWindow


# *****************************************************************************
# Main
# *****************************************************************************
def main():
	# Init log
	logging.info('Begin')
 
	try:
		reader_add_plugins()
	except Exception as e:
		print(f"No reader plugin, {e}")
		pass

	# Parse parse_args
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument( 'directory_list', 
					 type=str, nargs='*', 
					 default='.', 
					 help="List of directories containing the processed scenarios,"
					            " glob module is used to generate a list from the input'"
						)
	parser.add_argument('-r','--report', help='Existing report file')
	parser.add_argument('-rd', '--root_dir',  type=str, default='', help='root directory for directory list')
	parser.add_argument('-rec', '--recursive',  action='store_true', help='recursively parse directories')
	parser.add_argument('-f',  '--filters', default='',
	                    help='Filter images containing the specified string: in case of jpg list filter on resulting '
							 'image name, in case of json, filter on input image name'+
	                         ' for the moment, you can use a list with commas')
	parser.add_argument('-s', '--suffix_list', default='',
	                    help='Comma separated list of suffixes, suffix is applying to corresponding directory or last '
							 'one if there is no corresponding directory')
	parser.add_argument('-c', '--config', type=str, default='default',
						help='Configuration file, if no configuration file is specified, it will use the '
							 'default one')
	parser.add_argument('--viewer', type=str, choices={'gl','qt','shader'}, default='qt',
						help="Viewer mode, qt: standard qt display, gl: use opengl,  shader: enable opengl with "
							 "shaders")
	parser.add_argument('--profile', action='store_true', help="Profile code with cProfile")
	parser.add_argument('--ext', nargs='+', default=['.jpg', '.png'], help="List of image extensions")
	parser.add_argument('--sets', nargs='+', default=[],
	                    help="List of of image sets, each image set is defined as name:dir:suffix, this parameter"
	                         "replacess directory_list and suffix_list options")
	parser.add_argument('--timing', action='store_true', help='display timings')

	args = parser.parse_args()
	_params = vars(args)

	need_image_sets = True
	if args.report is not None:
		# read json file and set parameters from it
		try:
			data = fill_table_data.readJson(args.report)
			for key in data['params']:
				# don't change report value
				if key == 'report':
					continue
				# keep command line argument if using long name: --XXX
				if key not in _params or _params[key] is None or _params[key] == '' \
						or '--'+key not in sys.argv:
					_params[key] = data['params'][key]
			# determine if we need to create the image_sets key in the params dictionary
			need_image_sets = 'image_sets' not in data['params']
		except Exception as e:
			print("Failed to read json report ", e)

	# Create image sets, pairs directory/suffix
	if need_image_sets:
		if _params['sets'] != []:
			image_sets = []
			# Use sets argument to define image sets
			for set_desc in _params['sets']:
				set_name, set_dir, set_suffix = set_desc.split(':')
				print(f"{set_name}, {set_dir}, {set_suffix}")
				if _params['root_dir'] != '':
					set_dir = os.path.join(_params['root_dir'], set_dir)
				image_sets.append(
					{
						'name': set_name,
						'directory': set_dir,
						'suffix': set_suffix
					}
				)
			_params['image_sets'] = image_sets
		else:
			# try to maintain compatibility to read older reports
			if _params['directory_list'] is None:
				_params['directory_list'] = ""
				if 'first_directory' in _params:
					_params['directory_list'] = _params['first_directory']
				if 'second_directory' in _params:
					_params['directory_list'] += ','+_params['second_directory']
			if _params['suffix_list'] is None:
				_params['suffix_list'] = ""
				if 'suffix1' in _params:
					_params['suffix_list'] = _params['suffix1']
				if 'suffix2' in _params:
					_params['suffix_list'] += ','+_params['suffix2']
			# create the list of (directory,suffix) pairs
			directories = _params['directory_list']
			print(f"{directories}")
			replaced_dir = []
			# use glob to replace directories containing special characters like * and ?
			for d in directories:
				replaced_dir.extend(glob.glob(d))
			directories = replaced_dir
			# Put the result back into _params for further use
			_params['directory_list'] = directories
			print(f"{directories}")
			suffixes    = _params['suffix_list'].split(',')
			list_size = max(len(directories), len(suffixes))
			image_sets = []
			for n in range(list_size):
				image_set = dict()
				current_directory = directories[min(n, len(directories) - 1)]
				if _params['root_dir'] != '':
					current_directory = os.path.join(_params['root_dir'], current_directory)
				image_set['directory'] = current_directory
				image_set['suffix']    = suffixes   [min(n, len(suffixes)-1)]
				image_sets.append(image_set)
			_params['image_sets'] = image_sets

	print("image_sets ", _params['image_sets'])

	# check if directory exist as standalone or exists as a subdirectory of the script path
	if args.report:
		search_path = os.path.dirname(os.path.realpath(args.report))
	else:
		search_path = os.getcwd()

	for pos, s in enumerate(_params['image_sets']):
		d = s['directory']
		if not os.path.isdir(d):
			# try as relative
			d1 = os.path.join(search_path, d)
			if os.path.isdir(d1):
				print("Found path {0}".format(d1))
				_params['image_sets'][pos]['directory'] = d1
			else:
				print("Path {0} or {1} not found".format(d, d1))
		else:
			print("Path {0} checked".format(d))

	# Read config file
	if os.path.isfile(_params['config']):
		config_filename = _params['config']
	else:
		filename = os.path.join(os.path.dirname(__file__), 'config', _params['config']+'.json')
		if os.path.isfile(filename):
			config_filename = filename
		else:
			print("config file not found")
			sys.exit(1)
	try:
		with open(config_filename, 'r') as cf:
			config = json.load(cf)
	except Exception as e:
		print(("Failed to open config file {} error: {}".format(config_filename, e)))

	_params['version'] = version.__version__

	if sys.platform.startswith("darwin"):
		try:  # set bundle name on macOS (app name shown in the menu bar)
			from Foundation import NSBundle
		except ImportError:
			pass
		else:
			bundle = NSBundle.mainBundle()
			if bundle:
				info = (bundle.localizedInfoDictionary() or bundle.infoDictionary())
				if info:
					info["CFBundleName"] = "IMCOMP"

	QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
	app = QtWidgets.QApplication(sys.argv)
	try:
		app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)
	except Exception as e:
		print("Attribute QtCore.Qt.AA_UseHighDpiPixmaps not available: {}".format(e))

	_params['config_name'] = config['config_name']

	mode = {
		'qt':        ViewerType.QT_VIEWER,
		'gl':        ViewerType.OPENGL_VIEWER,
		'shader':    ViewerType.OPENGL_SHADERS_VIEWER
	}[_params['viewer']]

	table_win = ImCompWindow( viewer_mode=mode)

	if _params['timing']:
		table_win.set_verbosity(table_win.verbosity_TIMING)
		table_win.set_verbosity(table_win.verbosity_TIMING_DETAILED)
	table_win.set_params(_params)
	table_win.fill_data(config)
	# If available, use 2nd screen
	screens = app.screens()
	if len(screens)>1:
		geometry = screens[1].geometry()
	else:
		geometry = screens[0].geometry()
	import copy
	new_geometry = copy.deepcopy(geometry)
	new_geometry.setSize(geometry.size()*0.9)
	new_geometry.moveCenter(geometry.center())
	print(f"{new_geometry}")
	table_win.setGeometry(new_geometry)
	table_win.raise_()
	# TODO: check if this line is needed
	table_win.multiview.update_image()


	print("_params['profile'] {}".format(_params['profile']))
	if _params['profile']:
		print("**** using cProfile")
		import cProfile
		res = cProfile.run('app.exec_()', "imcomp.prof")
		exit(res)
	else:
		sys.exit(app.exec())

if __name__ == '__main__':
    main()
