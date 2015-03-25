#!/usr/local/sci/bin/python2.7
"""
Module for handling monthly and seasonal forecasts by taking user input from
web based tool.
Module has 3 main capabilities: loading, modifying and exporting data.
Throughout the module, forecast data which is yet to be modified is called
"raw" data while modified data is called "modified".

Author: S Stanley
Date: December 2014

"""
import cgi
import cgitb
from DataSets import IssuedForecastData
from stats_functions import pdf_percentile_boundaries, \
                            percentile_boundaries, \
                            calculate_pdf_limits, \
                            pdf_probabilities, \
                            category_probabilities, \
                            spread_data, \
                            shift_data, \
                            blend_data
import scipy.stats
import numpy
import os
import json

import_directory = '../example_data/'
export_directory = '/net/windows/m-drive/metoffice/Production/Operations_Centre/_Public_Write/3_Month_Outlook/Exported_Data/'
temp_directory   = '/home/h02/sstanley/temp/'

VARS = ['precip', 't2m']
PERS = ['mon', 'seas']

label_dict = {'seas'   : '3M',
              'mon'    : '1M',
              't2m'    : 'Temp',
              'precip' : 'Ppn'}

period_dict = {'Jan' : {'seas' : 'FMA',
                        'mon'  : 'Feb'},
               'Feb' : {'seas' : 'MAM',
                        'mon'  : 'Mar'},
               'Mar' : {'seas' : 'AMJ',
                        'mon'  : 'Apr'},
               'Apr' : {'seas' : 'MJJ',
                        'mon'  : 'May'},
               'May' : {'seas' : 'JJA',
                        'mon'  : 'Jun'},
               'Jun' : {'seas' : 'JAS',
                        'mon'  : 'Jul'},
               'Jul' : {'seas' : 'ASO',
                        'mon'  : 'Aug'},
               'Aug' : {'seas' : 'SON',
                        'mon'  : 'Sep'},
               'Sep' : {'seas' : 'OND',
                        'mon'  : 'Oct'},
               'Oct' : {'seas' : 'NDJ',
                        'mon'  : 'Nov'},
               'Nov' : {'seas' : 'DJF',
                        'mon'  : 'Dec'},
               'Dec' : {'seas' : 'JFM',
                        'mon'  : 'Jan'}}

def print_response(response_json):
    """
    Print HTTP response.

    """
    print "Content-Type: text/html"
    print
    print response_json

def convert_json_to_dictionary(str_json):
    """
    Take a JSON and convert to a Python dictionary.

    """
    try:
        data_dict = json.loads(str_json)
    except ValueError:
        raise ValueError('Invalid JSON format: %s' % str_json)
    return data_dict

def convert_dictionary_to_json(dictionary):
    """
    Take a Python dictionary and convert to a JSON.

    """
    return json.dumps(dictionary, sort_keys=True, indent=4,
                      separators=(',', ': '))

def load_response(fcast_data, mem_nums, fcast_pdf_vals, fcast_probs,
                   climatology, clim_pdf_vals, pdf_points, clim_quintiles,
                   last_ten):
    """
    Create dictionary of all data. This is the format readable by the
    seasonal forecast PDF web page.

    """
    return {"raw_forecast" : {"values"     : list(fcast_data),
                              "mem_nums"   : list(mem_nums),
                              "pdf_vals"   : list(fcast_pdf_vals),
                              "pdf_points" : list(pdf_points),
                              "quin_probs" : fcast_probs},
            "climatology"  : {"values"     : list(climatology),
                              "pdf_vals"   : list(clim_pdf_vals),
                              "pdf_points" : list(pdf_points),
                              "quintiles"  : list(clim_quintiles)},
            "last_ten"     : {"values"     : list(last_ten)},
            "status"       : "success"}

def modify_response(modified_data, pdf_vals, fcast_probs,
                      clim_pdf_vals, pdf_points, clim_quintiles):
    """
    Create dictionary with modified data. This is the format readable by the
    seasonal forecast PDF web page.

    """
    return {"modified_forecast" : {"values"     : list(modified_data),
                                   "pdf_vals"   : list(pdf_vals),
                                   "pdf_points" : list(pdf_points),
                                   "quin_probs" : fcast_probs},
            "climatology"       : {"pdf_vals"   : list(clim_pdf_vals),
                                   "pdf_points" : list(pdf_points),
                                   "quintiles"  : list(clim_quintiles)},
            "status"            : "success"}

class PairedLists(object):
    """
    Class for lists which change in sync.

    Kwargs:

    * paired_lists: lists and there names
        Provide key word arguments of the list names and the lists themselves.

    """
    def __init__(self, **paired_lists):
        self.paired_lists = paired_lists

        list_len = None
        for name, lst in self.paired_lists.items():
            if list_len:
                assert len(lst) == list_len, 'All lists must have the same '\
                'length.'
            else:
                list_len = len(lst)
            setattr(self, name, lst)

    def __setattr__(self, name, value):
        """
        If one list is rearranged, find out how and do the same for all other
        lists.

        """
        # For when attributes are being changed after initialisation.
        if hasattr(self, name):
            current_list = numpy.array(getattr(self, name))
            new_list     = numpy.array(value)
            assert sorted(current_list) == sorted(new_list), 'The values in '\
            'paired lists can not be changed, only rearranged'

            index_mapping = []
            for val in new_list:
                indices = numpy.where(current_list == val)
                for index in indices[0]:
                    if index not in index_mapping:
                        index_mapping.append(index)
                        break

            for lst_name, lst in self.paired_lists.items():
                new_lst = [lst[i] for i in index_mapping]
                self.__dict__[lst_name] = new_lst

        # For initialisation (when setting attributes for the first time).
        else:
            self.__dict__[name] = value

class LoadData(object):
    """
    Class which loads relevant data and stores it as attributes.

    Args:

    * main_dir: string
        This is the directory were all the completed data is stored. This
        directory is only ever read from.

    * variable: string
        Specify the variable, 't2m' for air temperature at 2 metres or 'precip'
        for precipitation.

    * period: string:
        Specify the period type of the forecast, either 'mon' for the monthly
        or 'seas' for the seasonal (3 months).

    * iss_month: string
        Specify the month the forecast was issued (not the month of the
        forecast), this is the month before the first forecasted month. Use the
        first 3 letters of the month e.g. 'Jan' or 'Feb'.

    * iss_year: integer
        Specify the year the forecast was issued, this is the year of the
        iss_month, not the year of the forecast period (if different).

    Kwargs:

    * clim_period: list
        Specify the year range which defines the climatology.

    * raw_data: boolean
        If True raw data is loaded regardless, If False, preference is taken to
        load modified data, if none is found, raw data is loaded.

    * export_dir_only: boolean
        If True, only the export_dir is searched for files (which will always
        be modified files) and an exception is raised if none are found.

    * export_dir: string
        The directory where current data is stored whilst it is being modified.

    """
    def __init__(self, main_dir, variable, period, iss_month, iss_year,
                 clim_period=[1981, 2010], raw_data=False,
                 export_dir_only=False, export_dir=''):

        self.main_dir   = main_dir
        self.export_dir = export_dir

        self.fcast = IssuedForecastData(variable, period, iss_month, iss_year,
                                        data_dir=self.export_dir)

        self.fcast_data, self.mem_numbers = self._get_fcast_data(
                                            raw_data=raw_data,
                                            export_dir_only=export_dir_only)
        if clim_period is None:
            source = 'file'
        else:
            source = 'ncic'
        self.clim_data  = self.fcast.climatology_obs_load(
                          source=source,
                          clim_period=clim_period)
        self.last_ten = self._get_last_ten(iss_month, iss_year)

    def _get_fcast_data(self, raw_data, export_dir_only):
        """
        Load the fcast data, try to get modified data first (unless specified
        by raw_data = True), if no modified data exists, load the raw data.
        Note, member numbers can only be retrieved with raw data.

        """
        if raw_data:
            # Raw data is always loaded from main_dir.
            self.fcast.data_dir = self.main_dir
            fcast_data, mem_nums = self.fcast.model_load(
                                        modified=False,
                                        get_member_numbers=True)
        else:
            mem_nums = []
            try:
                # Try to load modified data from export_dir (set in __init__)
                # first. This is where recently modified data is kept before
                # final exporting to main_dir.
                fcast_data = self.fcast.model_load(modified=True)
            except IOError as err_message:
                if export_dir_only:
                    raise IOError(err_message)
                else:
                    try:
                        # If there's nothing there, try to load modified data
                        # from main_dir.
                        self.fcast.data_dir = self.main_dir
                        fcast_data = self.fcast.model_load(modified=True)
                    except IOError:
                        # If not get the unmodified from main_dir.
                        self.fcast.data_dir = self.main_dir
                        fcast_data = self.fcast.model_load(modified=False)
        return fcast_data, mem_nums

    def _get_last_ten(self, iss_month, iss_year):
        """
        Retrieve the forecast data, observation climatology and observations
        for the last ten years.

        """
        if iss_month.lower() == 'dec':
            year = int(iss_year) + 1
        else:
            year = int(iss_year)
        last_ten_years = range(year-10, year)
        last_ten = self.fcast.climatology_obs_load(
                   clim_period=last_ten_years)
        return last_ten

class ForecastPDFHandler(object):
    """
    Class for modifying forecast data, creating PDF's of it and
    calculating probabilities

    Args:

    * fcast_data: array like

    * clim_data: array like

    """
    def __init__(self, fcast_data, clim_data):
        self.fcast_data     = fcast_data
        self.clim_data      = clim_data
        self.fcast_pdf      = None
        self.clim_pdf       = None
        self.fcast_pdf_vals = None
        self.clim_pdf_vals  = None
        self.pdf_points     = None

    def calculate_pdfs(self, levels=101, range_limiter=40,
                         bandwidth='silverman'):
        """
        Calculates the PDFs for the fcast data and climatology data, as well as
        a number of PDF values (how many is determined by self.levels) and the
        associated PDF points i.e. the x (points) and y (values) of each PDF
        but the x is the same for both, this is just self.pdf_points.

        Kwargs:

        * levels : integer
            This determines how many points are returned. If plotting, higher
            values lead to smoother plots.

        * range_limiter: scalar
            This value is used to calculate the range of the PDF. A PDF function
            can take a while to converge to 0, so to calculate sensible stop and
            start points, some proportional value above 0 is calculated. The given
            range_limiter value is used as factor to determine what that above 0
            value is. Simply, the higher the given value the wider the PDF limits.
            See nested function calculate_pdf_limits for more details.

        * bandwidth: string, scalar or callable
            The method used to calculate the estimator bandwidth. This can be
            'scott', 'silverman', a scalar constant or a callable. If a scalar,
            this will be used directly as kernel-density estimate (kde) factor.
            If a callable, it should take a scipy.stats.gaussian_kde instance
            as only parameter and return a scalar. Default is 'silverman'.

        """
        self.fcast_pdf = scipy.stats.gaussian_kde(self.fcast_data,
                                                  bw_method=bandwidth)
        self.clim_pdf  = scipy.stats.gaussian_kde(self.clim_data,
                                                  bw_method=bandwidth)
        mod_min, mod_max = calculate_pdf_limits(self.fcast_pdf,
                                                levels,
                                                range_limiter)
        clm_min, clm_max = calculate_pdf_limits(self.clim_pdf,
                                                levels,
                                                range_limiter)
        dmin = min(mod_min, clm_min)
        dmax = max(mod_max, clm_max)
        self.pdf_points = numpy.linspace(dmin, dmax, levels)
        self.fcast_pdf_vals = self.fcast_pdf(self.pdf_points)
        self.clim_pdf_vals  = self.clim_pdf(self.pdf_points)

    def get_percentile_bounds(self, bounds_from='pdf', num_of_cats=5):
        """
        Calculate the percentile boundaries defined by the climatology. Bounds
        can be calculated from the PDF (must have run calculate_pdfs method) or
        the data.

        Kwargs:

        * bounds_from: 'pdf' or 'data'

        * num_of_cats: integer
            How many categories to split data into, num_of_cats - 1 values are
            always returned.

        Returns:
            list

        """
        assert bounds_from in ['pdf', 'data'], 'Invalid bounds_from argument '\
        '%s. Must be either "pdf" or "data".' % bounds_from
        assert num_of_cats > 1, 'There must be two or more categories in '\
        'order to split the data.'

        if bounds_from == 'pdf':
            assert self.clim_pdf, 'PDFs have not been calculated. Use '\
            'calculate_pdfs method or set bounds_from to "data".'
            clim_percentiles = pdf_percentile_boundaries(self.clim_pdf,
                                                         num_of_cats)
        else:
            clim_percentiles = percentile_boundaries(self.clim_data, num_of_cats)
        return clim_percentiles

    def calculate_forecast_probs(self, bounds, probs_from='pdf'):
        """
        Calculate the forecast probability for each category defined by the
        bounds. Either the forecast PDF or the forecast data can be used.

        Args:

        * bounds: list

        Kwrgs:

        * probs_from: 'pdf' or 'data'

        Returns:
            list

        """
        assert probs_from in ['pdf', 'data'], 'Invalid probs_from argument '\
        '%s. Must be either "pdf" or "data".' % probs_from

        if probs_from == 'pdf':
            assert self.fcast_pdf, 'PDFs have not been calculated. Use '\
            'calculate_pdfs method or set probs_from to "data".'
            fcast_probs = pdf_probabilities(self.fcast_pdf, bounds)
        else:
            fcast_probs = category_probabilities(self.fcast_data, bounds)
        return fcast_probs


    def overwrite_data(self, overwrites):
        """
        Method to replace specific values in the forecast data.

        Args:

        * overwrites: list of dictionaries
            Each dictionary must use a specific format with these keys:
            {"val_indx": index of value to overwrite ,
             "new_val": value with which to overwrite }

        """
        for overwrite in overwrites:
            self.fcast_data[overwrite["val_indx"]] = overwrite["new_val"]

    def modify_forecast_data(self, spread=1, shift=0, blend=0):
        """
        Modify the forecast data in three ways, spread, shift and blend.

        Kwargs:

        * spread: float
            A scalar value of how much to adjust the spread of the data.

        * shift: float
            A value of how much to shift the data.

        * blend: float
            A percentage value of how much to blend to climatology.

        """
        if spread != 1:
            self.fcast_data = spread_data(self.fcast_data, spread)
        if shift != 0:
            self.fcast_data = shift_data(self.fcast_data, shift)
        if blend != 0:
            self.fcast_data = blend_data(self.fcast_data, self.clim_data,
                                         blend)


class ExportHandler(object):
    """
    Class for saving forecast data in specific format.

    Args:

    * variable: string

    * iss_month: string
        Name of month when forecast was issued, e.g. 'Jan'

    * iss_year: integer
        Year when forecast was issued.

    * period: string 'mon' or 'seas'

    * last_ten_vals: list

    * last_ten_years: list

    * clim_data: list

    * fcast_data: list

    * mem_numbers: list
        Note, it is assumed that the values in mem_numbers correspond with the
        values in fcast_data directly. I.e. the first value in mem_numbers is
        the member number for the first value in fcast_data, and so on.

    * pdf_points: list

    * fcast_pdf_vals: list

    * clim_pdf_vals: list

    * percentiles: list

    * export_dir: string
        Directory to save the resulting file. Note, filenames are generated
        by the class so only specify the directory, not the filename.

    """
    def __init__(self, variable, iss_month, iss_year, period, last_ten_vals,
                  last_ten_years, clim_data, fcast_vals, mem_numbers,
                  pdf_points, fcast_pdf_vals, clim_pdf_vals, percentiles,
                  export_dir=''):
        self.variable  = variable.lower()
        self.iss_month = iss_month.title()
        self.iss_year  = iss_year
        self.period    = period.lower()
        self.export_dir  = export_dir
        self.period_name = self._get_period_name()

        self.clim_data   = clim_data

        self.last_ten_data = PairedLists(last_ten_vals=last_ten_vals,
                                         last_ten_years=last_ten_years)
        self.last_ten_data.last_ten_vals = sorted(last_ten_vals)[::-1]

        self.fcast_data = PairedLists(fcast_vals=fcast_vals,
                                      mem_numbers=mem_numbers)
        self.fcast_data.fcast_vals = sorted(fcast_vals)[::-1]

        (self.pdf_points,
         self.clim_pdf_values,
         self.forecast_pdf_values) = self._sort_pdf_values(pdf_points,
                                                           clim_pdf_vals,
                                                           fcast_pdf_vals)
        self.percentiles = sorted(percentiles)[::-1]
        self.header_dict = self._create_header_dict()

    def _create_header_dict(self):
        """
        The output file can contain any combination of the following headers.

        """
        return {'last_10_vals'  : {'label' : '10Y CLIMATE',
                                   'round' : 1,
                                   'data'  : self.last_ten_data.last_ten_vals},
                'last_10_years' : {'label' : '10Y LABELS',
                                   'round' : 0,
                                   'data'  : self.last_ten_data.last_ten_years},
                'clim_vals'     : {'label' : '30Y CLIMATE',
                                   'round' : 2,
                                   'data'  : self.clim_data},
                'forecast_vals' : {'label' : 'MODFC',
                                   'round' : 10,
                                   'data'  : self.fcast_data.fcast_vals},
                'mem_numbers'   : {'label' : 'MEM NUMS',
                                   'round' : 0,
                                   'data'  : self.fcast_data.mem_numbers},
                'pdf_points'    : {'label' : '%s%s' % (
                                             label_dict[self.period],
                                             label_dict[self.variable]),
                                   'round' : 2,
                                   'data'  : self.pdf_points},
                'clim_pdf'      : {'label' : 'ClimPdf',
                                   'round' : 10,
                                   'data'  : self.clim_pdf_values},
                'forecast_pdf'  : {'label' : 'FcPdf',
                                   'round' : 10,
                                   'data'  : self.forecast_pdf_values},
                'percentiles'   : {'label' : 'PdfQuintiles',
                                   'round' : 10,
                                   'data'  : self.percentiles}}

    def _get_period_name(self):
        """
        Using the period_dict, return the name of the forecast period.

        """
        return period_dict[self.iss_month][self.period]

    def _sort_last_ten(self, values, years):
        """
        Order values and re-order years to match.

        """
        # Pair together values and years with a dictionary.
        last_ten = {}
        for value, year in zip(values, years):
            last_ten[value] = year

        last_ten_vals  = sorted(values)[::-1]
        last_ten_years = [last_ten[value] for value in last_ten_vals]
        return last_ten_vals, last_ten_years

    def _sort_pdf_values(self, pdf_points, clim_pdf_values,
                           forecast_pdf_values):
        """
        Order PDF values by the points and re-order clim and forecast values to
        match.

        """
        pdf_dict = {}
        for point, clim_val, fcst_val in zip(pdf_points,
                                             clim_pdf_values,
                                             forecast_pdf_values):
            pdf_dict[point] = {}
            pdf_dict[point]['clim_val'] = clim_val
            pdf_dict[point]['fcst_val'] = fcst_val

        pdf_points      = sorted(pdf_points)[::-1]
        clim_pdf_values = [pdf_dict[value]['clim_val'] for value in pdf_points]
        fcst_pdf_values = [pdf_dict[value]['fcst_val'] for value in pdf_points]
        return pdf_points, clim_pdf_values, fcst_pdf_values

    def _extend_filename(self, filename, addition):
        """
        Add a string to the given filename but placing it before the extension
        if there is one.

        """
        filename_parts = filename.split('.')
        if len(filename_parts) == 1:
            index = 0
        else:
            index = -2
        filename_parts[-2] = filename_parts[index] + addition
        return '.'.join(filename_parts)

    def _create_header_string(self, separator, length, header_str='OUTPUT'):
        """
        Each column of the file starts with header_str.

        """
        return ''.join([header_str + separator] * length) + '\n'

    def _sort_data_to_write(self, data_headers, separator, tab_spaces):
        """
        Sort data so it is formatted appropriately.
        Only one of the arguments, separator or tab_spaces should be provided.
        If both are given tab_spaces is ignored, if neither are given,
        tab_spaces is used and set to 1.

        """
        sorted_labels = ''
        sorted_data   = []
        num_of_lines  = 0

        for header in data_headers:
            data_dict = self.header_dict.get(header)
            if data_dict is None:
                raise UserWarning('"%s" is not a valid header name. Use '\
                                  'print_data_headers method to see available'\
                                  ' header names.' % header)

            label      = data_dict['label']
            data       = data_dict['data']
            rounding   = data_dict['round']
            str_format = '%.0'+str(rounding)+'f'

            # Sort the labels and data by calculating the appropriate separator.
            if separator == '\t':
                if tab_spaces is None:
                    tab_spaces = 1
                # Calculate how many tabs must be appended to the label to
                # make the required spacing given by tab_spaces.
                label_num_of_tabs = max(tab_spaces - (len(label) // 8), 1)
                label_separator = '\t' * label_num_of_tabs

                # Calculate how many tabs must be appended to the data.
                data_num_of_tabs = max(tab_spaces - (rounding // 8), 1)
                data_separator = '\t' * data_num_of_tabs
            else:
                label_separator = data_separator = separator

            sorted_labels += (label + label_separator)
            sorted_data.append([str_format % val + data_separator
                                for val in data])

            # Calculate the number of lines of the file the data will use by
            # getting the maximum data length.
            if len(data) > num_of_lines:
                num_of_lines = len(data)

        sorted_labels += '\n'

        return sorted_labels, sorted_data, num_of_lines

    def _create_data_string(self, all_data, num_of_lines, separator):
        """
        Append all data to a string, filling gaps where columns have stopped
        with a solitary separator string.

        """
        data_str = ''
        for i in xrange(num_of_lines):
            for data in all_data:
                try:
                    data_str += data[i]
                except IndexError:
                    # If the data list has finished put separator in instead.
                    data_str += separator
            data_str += '\n'
        return data_str

    def _write_file(self, outfile, data_headers, separator, tab_spaces,
                     additional_labels):
        """
        Write the given data and headers to a .dat file using tab spaces to
        separate columns.

        """
        if tab_spaces:
            full_separator = '\t' * tab_spaces
        else:
            full_separator = separator
        headers = self._create_header_string(full_separator, len(data_headers))
        labels, all_data, num_of_lines = self._sort_data_to_write(
                                         data_headers, separator,
                                         tab_spaces)
        data_str = self._create_data_string(all_data, num_of_lines,
                                            full_separator)

        outfile.write(headers)
        outfile.write(labels)
        if additional_labels:
            additional_label_str = ''
            for label in additional_labels:
                if separator == '\t':
                    label_num_of_tabs = max(tab_spaces - (len(label) // 8), 1)
                    label_separator = '\t' * label_num_of_tabs
                else:
                    label_separator = separator
                additional_label_str += label + label_separator
            additional_label_str += '\n'
            outfile.write(additional_label_str)
        outfile.write(data_str)

    def _join_files(self, filename, original_filename, separator, tab_spaces,
                     leave_space):
        """
        Join the contents of the two files by placing the new data (filename)
        in new columns to the right of the existing data (original_filename).

        """
        if tab_spaces:
            full_separator = separator * tab_spaces
        else:
            full_separator = separator
        # Create a new file in which to write the contents of the original
        # and additional data files together.
        temp_filename = self._extend_filename(filename, 'temp')
        with open(self.export_dir + original_filename, 'r') as orig_file:
            with open(self.export_dir + filename, 'r') as additional_file:
                orig_file_lines = orig_file.readlines()
                add_file_lines  = additional_file.readlines()
                # Both files must contain the same number of lines to merge
                # properly.
                num_of_lines = max(len(orig_file_lines),
                                   len(add_file_lines))
                orig_diff = num_of_lines - len(orig_file_lines)
                add_diff  = num_of_lines - len(add_file_lines)
                if orig_diff > 0:
                    # Account for \n string which adds one to line length.
                    line_length = len(
                                  orig_file_lines[0].split(full_separator)) \
                                  - 1
                    orig_file_lines += [full_separator * line_length + '\n'] \
                                       * orig_diff
                elif add_diff > 0:
                    line_length = len(
                                  add_file_lines[0].split(full_separator)) \
                                  - 1
                    add_file_lines += [full_separator * line_length + '\n'] \
                                      * add_diff
                if not leave_space:
                    # If a space is not required between columns, the
                    # separator can now be changed to blank (it's original
                    # value is no longer needed for the rest of this function).
                    full_separator = ''

                with open(self.export_dir + temp_filename, 'w') as outfile:
                    for i in xrange(num_of_lines):
                        # Remove \n from each line of original file with
                        # [:-1] and replace with the separator.
                        orig_file_lines[i] = orig_file_lines[i][:-1] + \
                                             full_separator + \
                                             add_file_lines[i]
                        outfile.write(orig_file_lines[i])
        # Remove what are now old files.
        os.remove(self.export_dir + original_filename)
        os.remove(self.export_dir + filename)
        # Rename the temporary file with the original filename,
        os.rename(self.export_dir + temp_filename,
                  self.export_dir + original_filename)
        return original_filename

    def create_dat_filename(self, variable=None, period=None):
        """
        Create filename with format used for main .dat export files.

        """
        if not variable:
            variable = self.variable
        if not period:
            period = self.period
        return '{m}{y}_{v}_adj{p}.dat'.format(m=self.iss_month,
                                              y=self.iss_year,
                                              v=variable,
                                              p=period)

    def create_paired_filename(self, period=None, temporary=False):
        """
        Create filename with format used for paired forecast .csv export files.

        """
        if period is None:
            period = self.period
        period_name = period_dict[self.iss_month][period]
        if temporary:
            temp = 'temp'
        else:
            temp = ''
        return 'For_{p}{y}_paired_forecasts{t}.csv'.format(p=period_name,
                                                           y=self.iss_year,
                                                           t=temp)

    def create_pdf_filename(self):
        """
        Create filename with format used for PDF .csv export files.

        """
        return 'EA_for_{p}{y}_{v}_pdf.csv'.format(p=self.period_name,
                                                  y=self.iss_year,
                                                  v=self.variable)

    def save_data(self, filename, data_headers, tab_spaces=1,
                   append_to_file=False, leave_space=False,
                   additional_labels=None):
        """
        Save the requested data to file. If the filename extension is .csv,
        commas instead of tabs will be used to separate columns.

        Args:

        * filename: string
            The filename (not the absolute file path) to use to save the data.
            Note, the absolute file path is given in the class initialisation
            by the key word argument export_dir.

        * data_headers: list
            List the headers of the data to be saved. The order the headers are
            given is the order they are saved in the file.

        Kwargs:

        * tab_spaces: integer
            Specify the (maximum) number of tab spaces between columns. If data
            is longer than a tab space then a tab space is removed so the data
            lines up. However there is always a minimum of 1 tab. This argument
            is ignored if a .csv filename is provided.

        * append_to_file: boolean
            If the file already exists, add the new data in new columns. Note,
            this appends new columns to the right not underneath the current
            content.

        * leave_space: boolean
            If append_to_file is set to True, this argument specifies whether
            to leaves a space (a comma or tabs depending on the file type) in
            between the current data and the new data.

        * addtional_labels: list
            Provide a list of additional labels to be plotted above the data.

        Returns:
            The absolute file path where the data was saved.

        """
        if filename[-4:] == '.csv':
            separator  = ','
            tab_spaces = None
        else:
            separator = '\t'

        if append_to_file:
            if os.path.exists(self.export_dir + filename):
                # To append the new data, firstly save it to a temporary file.
                # The original and temporary files are later joined.
                original_filename = filename
                filename = self._extend_filename(filename, 'additional_data')
            else:
                # If the file does not already exist, carry on as normal.
                append_to_file = False

        with open(self.export_dir + filename, 'w') as outfile:
            self._write_file(outfile, data_headers, separator, tab_spaces,
                             additional_labels)

        if append_to_file:
            filename = self._join_files(filename, original_filename, separator,
                                        tab_spaces, leave_space)
        return self.export_dir + filename

    def print_data_headers(self):
        """
        Print all valid data headers.

        """
        for header in self.header_dict.keys():
            print header

    def saved_dat_files(self, variables, periods):
        """
        Check to see if all combinations of data have been saved.

        Args:

        * variables: list
            List of valid meteorological variable names.

        * periods: list
            List of valid period names.

        Returns:
            boolean

        """
        files_exist = []
        for var in variables:
            for period in periods:
                test_filepath = self.export_dir + \
                                self.create_dat_filename(var, period)
                if os.path.exists(test_filepath):
                    files_exist.append(True)
                else:
                    files_exist.append(False)
        return numpy.array(files_exist)

def load_data(data_dict):
    """
    Load the raw forecast data.

    """
    data = LoadData(import_directory, data_dict['variable'],
                    data_dict['period'], data_dict['iss_month'],
                    data_dict['iss_year'], data_dict['clim_period'],
                    data_dict['raw_data'], export_dir=export_directory)

    data_handler = ForecastPDFHandler(data.fcast_data, data.clim_data)
    data_handler.calculate_pdfs(data_dict['levels'],
                               data_dict['range_limiter'],
                               data_dict['bandwidth'])
    bounds = data_handler.get_percentile_bounds(data_dict['bounds_from'], 5)
    fcast_probs = data_handler.calculate_forecast_probs(bounds, 'pdf')

    response_dict = load_response(data_handler.fcast_data,
                                  data.mem_numbers,
                                  data_handler.fcast_pdf_vals,
                                  fcast_probs,
                                  data.clim_data,
                                  data_handler.clim_pdf_vals,
                                  data_handler.pdf_points,
                                  bounds,
                                  data.last_ten)
    print_response(convert_dictionary_to_json(response_dict))

def modify_data(data_dict):
    """
    Modify the raw forecast data.

    """
    data_handler = ForecastPDFHandler(data_dict['fcast_data'],
                                      data_dict['clim_data'])
    data_handler.modify_forecast_data(data_dict['spread'],
                                      data_dict['shift'],
                                      data_dict['blend'])
    if data_dict['overwrites']:
        data_handler.overwrite_data(data_dict['overwrites'])

    data_handler.calculate_pdfs(data_dict['levels'],
                               data_dict['range_limiter'],
                               data_dict['bandwidth'])
    bounds = data_handler.get_percentile_bounds(data_dict['bounds_from'], 5)
    fcast_probs = data_handler.calculate_forecast_probs(bounds, 'pdf')

    response_dict = modify_response(data_handler.fcast_data,
                                    data_handler.fcast_pdf_vals,
                                    fcast_probs,
                                    data_handler.clim_pdf_vals,
                                    data_handler.pdf_points,
                                    bounds)
    print_response(convert_dictionary_to_json(response_dict))

def export_data(data_dict):
    """
    Write the modified data to file. Note, modification doesn't need to have
    been done.

    """
    exporter = ExportHandler(variable=data_dict['variable'],
                             iss_month=data_dict['iss_month'],
                             iss_year=data_dict['iss_year'],
                             period=data_dict['period'],
                             last_ten_vals=data_dict['last_ten_vals'],
                             last_ten_years=data_dict['last_ten_years'],
                             clim_data=data_dict['clim_data'],
                             fcast_vals=data_dict['fcast_data'],
                             mem_numbers=data_dict['mem_numbers'],
                             pdf_points=data_dict['pdf_points'],
                             fcast_pdf_vals=data_dict['forecast_pdf_vals'],
                             clim_pdf_vals=data_dict['clim_pdf_vals'],
                             percentiles=data_dict['quintiles'],
                             export_dir=export_directory)

    # Create all filenames including temporary filenames for paired data.
    month_fname  = exporter.create_paired_filename(period='mon',
                                                   temporary=True)
    seas_fname   = exporter.create_paired_filename(period='seas',
                                                   temporary=True)
    paired_fname = exporter.create_paired_filename(period='seas')
    precip_pdf_filename = exporter.create_pdf_filename()
    dat_filename = exporter.create_dat_filename()

    # If no .dat files exists, there should be no .csv files.
    if not exporter.saved_dat_files(VARS, PERS).any():
        for fname in [month_fname, seas_fname, paired_fname,
                      precip_pdf_filename]:
            if os.path.exists(exporter.export_dir + fname):
                os.remove(exporter.export_dir + fname)

    # Check the current .dat doesn't already exist.
    if os.path.exists(exporter.export_dir + dat_filename):
        os.remove(exporter.export_dir + dat_filename)

    # Save .dat file
    exporter.save_data(dat_filename, ['last_10_vals',
                                     'last_10_years',
                                     'clim_vals',
                                     'forecast_vals',
                                     'pdf_points',
                                     'clim_pdf',
                                     'forecast_pdf',
                                     'percentiles'])

    temp_paired_fname = exporter.create_paired_filename(temporary=True)
    additional_lab = '%s %s' % (label_dict[exporter.period],
                                label_dict[exporter.variable])
    # Sort by member number order (sorting this list automatically re orders
    # the forecast value list becuase they are paired).
    exporter.fcast_data.mem_numbers = sorted(exporter.fcast_data.mem_numbers)
    # Reload the header dictionary to update reordering.
    exporter.header_dict = exporter._create_header_dict()
    exporter.save_data(temp_paired_fname, ['clim_vals',
                                           'forecast_vals'],
                       append_to_file=True,
                       additional_labels=[additional_lab,
                                          additional_lab])

    # If all .dat files exists, join paired files together.
    if exporter.saved_dat_files(VARS, PERS).all():
        temp_filename = exporter._join_files(seas_fname, month_fname,
                                             separator=',', tab_spaces=None,
                                             leave_space=True)
        os.rename(exporter.export_dir + temp_filename,
                  exporter.export_dir + paired_fname)


    if exporter.variable == 'precip' and exporter.period == 'seas':
        exporter.save_data(precip_pdf_filename, ['pdf_points',
                                                 'clim_pdf',
                                                 'forecast_pdf'])

    response_dict = {'status'   : 'success',
                     'response' : exporter.export_dir + dat_filename}
    print_response(convert_dictionary_to_json(response_dict))

def main(str_json):
    """
    Depending on the given request type, load, modify or export the forecast
    data. The contents of the data dictionary (created from the received JSON)
    is specific to the request type, e.g. a load_data request contains dates
    and variable names descriping which data to load while an export_data
    request contains actual data.

    """
    data_dict = convert_json_to_dictionary(str_json)

    if data_dict['request_type'] == 'load_data':
        load_data(data_dict)

    elif data_dict['request_type'] == 'modify_data':
        modify_data(data_dict)

    elif data_dict['request_type'] == 'export_data':
        export_data(data_dict)

if __name__ == '__main__':

    cgitb.enable()
    # Read in JSON query string sent from web tool.
    form = cgi.FieldStorage()
    str_json = form['query'].value

    try:
        main(str_json)
    except Exception as err_message:
        response_dict = {'status' : 'failed',
                         'response' : str(err_message)}
        print_response(convert_dictionary_to_json(response_dict))

# Example JSONs for testing and debugging.
#
#    load_json = '{"request_type":"load_data",'\
#                '"variable":"t2m",'\
#                '"iss_month":"Jan",'\
#                '"iss_year":"2016",'\
#                '"period":"mon",'\
#                '"levels":101,'\
#                '"range_limiter":40,'\
#                '"bandwidth":"silverman",'\
#                '"clim_period":[1981,2010],'\
#                '"raw_data":true,'\
#                '"bounds_from":"pdf"}'
#    main(load_json)
#
#    modf_json = '{"request_type":"modify_data",'\
#                '"fcast_data":[6.21,6.14,5.92,5.81,5.81,5.81,5.69,5.65,5.57,5.54,5.45,5.44,5.17,5.12,5.11,5.07,4.79,4.76,4.73,4.69,4.61,4.56,4.45,4.39,4.37,4.36,4.34,4.27,4.25,4.22,4.18,4.14,4.01,3.98,3.67,3.58,3.05,2.84,2.01],'\
#                '"clim_data":[6.83,5.94,5.46,5.23,5.16,4.99,4.9,4.89,4.86,4.78,4.71,4.41,4.29,4.19,3.86,3.69,3.68,3.52,3.42,3.37,3.17,3.03,2.62,2.38,2.22,2.01,1.91,1.39,1.35,-1.16],'\
#                '"spread":3,'\
#                '"shift":-6,'\
#                '"blend":35,'\
#                '"overwrites":[{"val_indx":1,"new_val":7.11}],'\
#                '"levels":50,'\
#                '"bandwidth":"silverman",'\
#                '"range_limiter":10}'
#    main(modf_json)
#
#    export_json = '{"request_type":"export_data",'\
#                    '"variable":"t2m",'\
#                    '"iss_month":"Apr",'\
#                   '"iss_year":"2014",'\
#                   '"period":"mon",'\
#                    '"last_ten_vals":[4.4,3.7,3.5,5.2,4.9,3.7,1.9,5.3,4.2,2.8],'\
#                    '"last_ten_years":[2004,2005,2006,2007,2008,2009,2010,2011,2012,2013],'\
#                    '"clim_data":[2.6,4.3,1.4,3.2,2.2,-1.2,3,3.9,4.9,5.9,1.4,4.8,4.7,2.4,4.9,2,5.2,6.8,4.2,5,3.4,5.5,3.4,4.4,3.7,3.5,5.2,4.9,3.7,1.9],'\
#                    '"mem_numbers":[0,1,2,3,16,17,18,19,20,13,14,15,22,23,24,25,26,21,4,5,6,7,8,9,10,11,12,27,30,31,32,33,34,35,36,37,38,28,29],'\
#                    '"fcast_data":[12,5.26,5.23,4.99,4.98,4.93,4.54,4.5,4.4,4.37,4.36,4.22,4.16,4.11,4.09,4.07,3.93,3.88,3.86,3.77,3.76,3.63,3.63,3.39,3.24,3.1,3.06,2.94,2.93,2.71,2.71,2.41,2.34,2.23,1.09,1.08,0.83,-0.28,-1.08],'\
#                    '"pdf_points":[-3.4178217821782195,-3.293465346534655,-3.1691089108910906,-3.0447524752475266,-2.920396039603962,-2.7960396039603976,-2.671683168316833,-2.5473267326732687,-2.4229702970297042,-2.2986138613861398,-2.1742574257425757,-2.0499009900990113,-1.9255445544554468,-1.8011881188118826,-1.676831683168318,-1.5524752475247539,-1.4281188118811894,-1.303762376237625,-1.1794059405940605,-1.0550495049504964,-0.930693069306932,-0.8063366336633675,-0.681980198019803,-0.5576237623762386,-0.4332673267326741,-0.3089108910891101,-0.1845544554455456,-0.06019801980198114,0.06415841584158333,0.1885148514851478,0.3128712871287118,0.4372277227722763,0.5615841584158408,0.6859405940594052,0.8102970297029697,0.9346534653465342,1.0590099009900986,1.183366336633663,1.3077227722772267,1.4320792079207911,1.5564356435643556,1.68079207920792,1.8051485148514845,1.929504950495049,2.0538613861386135,2.178217821782178,2.3025742574257424,2.426930693069307,2.5512871287128713,2.675643564356435,2.7999999999999994,2.924356435643564,3.0487128712871283,3.173069306930693,3.2974257425742572,3.4217821782178217,3.546138613861386,3.6704950495049506,3.794851485148515,3.9192079207920787,4.043564356435644,4.167920792079208,4.2922772277227725,4.416633663366337,4.5409900990099015,4.665346534653466,4.78970297029703,4.914059405940595,5.038415841584159,5.162772277227724,5.287128712871288,5.411485148514853,5.535841584158417,5.660198019801982,5.784554455445546,5.908910891089109,6.033267326732673,6.157623762376238,6.281980198019802,6.406336633663367,6.530693069306931,6.655049504950496,6.77940594059406,6.903762376237625,7.028118811881189,7.1524752475247535,7.276831683168318,7.401188118811882,7.525544554455447,7.649900990099011,7.774257425742576,7.89861386138614,8.022970297029705,8.14732673267327,8.271683168316834,8.396039603960398,8.520396039603963,8.644752475247525,8.76910891089109,8.893465346534654,9.017821782178219],'\
#                   '"forecast_pdf_vals":[0.00015231214064012594,0.00024342215221139694,0.0003796014642217655,0.0005776939579912344,0.0008581031636334616,0.0012443240915687307,0.001761866917923075,0.0024364980087330443,0.003291825975470943,0.004346395545245549,0.005610598896068065,0.007083841677756795,0.008752474321028504,0.010588988685031369,0.012552870271734216,0.014593292601795465,0.016653570043591606,0.018676991879604667,0.02061339354052216,0.022425626139248745,0.024094995873825558,0.025624779155884764,0.027041083880998826,0.02839061977019749,0.029735350060888493,0.031144496899046404,0.03268491192386082,0.03441131616127493,0.03635824260055676,0.038535552848950716,0.040929044730062814,0.043506891308535925,0.04623153291010289,0.04907537984879119,0.0520375615348732,0.05515828666684416,0.05852740271001589,0.062284555263097986,0.06660984562537342,0.07170577167382768,0.07777308768192394,0.08498458482444436,0.09346132430369901,0.10325539213415365,0.1143418734131081,0.12662077508842232,0.1399275215964795,0.15404890699796595,0.16874042592251973,0.18374095394139556,0.19878179388808795,0.21358889374303527,0.22787913394893805,0.24135345365330488,0.25369075445039874,0.2645466676847896,0.27356032779913064,0.2803704669634929,0.28463987537061974,0.2860851203633294,0.28450692404094124,0.2798161298200165,0.2720508387374854,0.26138186805484875,0.24810575187756972,0.23262654357331794,0.21542922909864023,0.1970483418887678,0.17803535304263482,0.15892778674950755,0.1402221007166297,0.12235149939957503,0.1056692335417381,0.09043764032244389,0.0768231001584948,0.06489704940848472,0.05464301895692701,0.04596927706576642,0.03872607278034851,0.03272584324324587,0.02776425673712284,0.02363978513224099,0.020169723992550768,0.01720118184714064,0.014616413420232684,0.012332783461511784,0.010298421786569156,0.00848511870572527,0.0068801484021715495,0.005478520205172636,0.004276738155403808,0.0032686268984036177,0.0024432830783678626,0.001784829819853082,0.0012734338130542535,0.0008869891771019406,0.0006029441236149091,0.00039989290977385033,0.00025872408075693835,0.00016326599528193066,0.00010047892696109695],'\
#                    '"clim_pdf_vals":[0.0006387047465874883,0.000901493770764208,0.001247365063065634,0.001691973956211465,0.0022499068481562578,0.0029329757747164216,0.003748253994105419,0.0046960372006083105,0.005767986668696713,0.006945759566498768,0.008200442053569325,0.009493060820721511,0.010776354462722479,0.011997843954904181,0.013104068963667025,0.014045680035565477,0.014782926314252837,0.01529098255918276,0.015564537394186324,0.015621122776976634,0.015502793085650151,0.015275937948996478,0.01502920499319505,0.014869685551963852,0.014917653637545786,0.015300234036421037,0.01614441127794324,0.017569791016411877,0.01968150843672844,0.022563662462821547,0.026273649523878,0.030837774232536513,0.036248512668223494,0.04246377560041544,0.049408441877425074,0.05697829147026713,0.06504626210988704,0.0734706990518205,0.08210499679450184,0.09080778907414992,0.0994526777515164,0.10793644527291009,0.11618479684106132,0.12415493153497821,0.13183462280303487,0.1392379470106453,0.1463982616661761,0.153359420408582,0.1601664436258851,0.1668568886644047,0.1734539669632099,0.17996206839242126,0.18636485158629426,0.19262555096298575,0.19868875335695613,0.2044827078557924,0.20992130433248837,0.2149051792448307,0.21932190580411345,0.22304577243924034,0.22593809911055004,0.22784925093612238,0.2286233992474658,0.22810664402235128,0.2261584236837789,0.2226653418424259,0.21755581510335323,0.2108134647824422,0.2024870637495098,0.19269515497813075,0.18162413834272167,0.16951955428595283,0.15667130259204845,0.14339443376982405,0.13000777831237642,0.11681293274901561,0.10407597396595614,0.09201377323871458,0.08078603708190597,0.07049335535083222,0.06118073380661023,0.05284545113743623,0.04544768932442452,0.03892227015445601,0.03318996912687152,0.028167211569487687,0.02377340204058336,0.01993560919674012,0.01659074687165098,0.013685702800589833,0.01117604176027965,0.009023950131046617,0.007196016900140396,0.005661299041659134,0.004389938947363643,0.003352426298052663,0.00251945473024431,0.001862230329151284,0.0013530472166588146,0.000965948157720451,0.0006773219837017489],'\
#                    '"quintiles":[2.246563473504463,3.394598625920879,4.306246004908942,5.239616417354868]}'
#    main(export_json)
