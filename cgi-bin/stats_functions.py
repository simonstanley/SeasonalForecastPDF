import numpy
import scipy.stats

def spread_data(data, scale):
    """
    Spread all the data points (from the mean) by the given scale.
    
    Args:
    
    * data: array like
    
    * scale: float
    
    Returns:
        array like
    
    """
    mean = numpy.mean(data)
    spread_data = []
    for val in data:
        spread_data.append(((val - mean) * scale) + mean)
    return spread_data

def shift_data(data, shift):
    """
    Shift all data points by given amount.
    
    Args:
    
    * data: array like
    
    * shift: float
    
    Returns:
        array like
        
    """
    return numpy.array(data) + shift

def blend_data(blend_data, fixed_data, blend):
    """
    Blend data towards fixed data using some crazy maths.
    
    Args:
    
    * blend_data: array like
        Data to be blended.
    
    * fixed_data: array like
        Data for which the blend_data is blended towards.
    
    * blend: float
        Percentage value of blend.
    
    Returns:
        array like
    
    """
    fcst_mean = numpy.mean(blend_data)
    fcst_std  = numpy.std(blend_data)
    clim_mean = numpy.mean(fixed_data)
    xbar_of_blend = (((100. - blend) * fcst_mean) + (blend * clim_mean)) / 100.
    xbar_2n = (xbar_of_blend ** 2) * 100.
    sx_2f = ((sum_of_squares(blend_data) * (100. - blend)) / len(blend_data)) \
            + ((sum_of_squares(fixed_data) * blend) / len(fixed_data))
    stdv_of_blend = ((sx_2f - xbar_2n) / 100.) ** 0.5
    blended_data = []
    for val in blend_data:
        adjusted_val = (((val - fcst_mean) / fcst_std) * stdv_of_blend) + \
                       xbar_of_blend
        blended_data.append(adjusted_val)
    
    return blended_data

def percentile_boundaries(data, num_of_categories):
    """
    Return the boundary values which split the given data set into the 
    requested number of categories. E.g. data = [1,2,3,4] split into 3 
    categories would return [2.0, 3.0] as the tercile boundaries.
    
    Args:
    
    * data: array like
    
    * num_of_categories: integer
        The number of categories wanted. Note, the function will always return
        num_of_categories - 1 values.
    
    Returns:
        list
    
    """
    percentiles = numpy.linspace(0, 100, num_of_categories+1)[1:-1]
    bounds = [round(numpy.percentile(data, percentile), 8)
              for percentile in percentiles]
    return bounds

def value_category(values, bounds, boundary_val_cat='outer', 
                     middle_val_cat='upper'):
    """
    Given a set of values and boundaries, return each value's category. 
    Categories are named numerically starting from 1. There are always 
    1 + number of bounds categories.
    
    Args:
    
    * values: float or list of floats
    
    * bounds: list
        A list of boundary values. These are automatically sorted into numeric 
        order.

    Kwargs:

    * boundary_val_cat:
        If a value equals a boundary value, specify whether it is placed in an 
        inner or outer category. Default is outer.
    
    * middle_val_cat:
        If a value equals the middle boundary value (only for odd number of 
        boundaries), specify whether it is placed in the upper or lower 
        category. Default is upper.
    
    Returns:
        list
    
    """
    if boundary_val_cat not in ['inner', 'outer']:
        raise ValueError('%s is not a valid input, use "inner" or "outer"' 
                         % boundary_val_cat)
    if middle_val_cat not in ['upper', 'lower']:
        raise ValueError('%s is not a valid input, use "upper" or "lower"' 
                         % middle_val_cat)
    if not hasattr(values, '__iter__'):
        values = [values]
    bounds.sort()
    num_of_bounds = len(bounds)
    middle_index  = float(num_of_bounds - 1) / 2.
    
    categories = []
    for value in values:
        category_found = False
        for index, bound in enumerate(bounds):
            if value > bound:
                continue
            elif value < bound:
                category_found = True
                categories.append(index + 1)
                break
            else:
                # When value equals a bound.
                if index < middle_index:
                    if boundary_val_cat == 'inner':
                        category = index + 2
                    else:
                        category = index + 1
                    category_found = True
                    categories.append(category)
                    break
                elif index > middle_index:
                    if boundary_val_cat == 'inner':
                        category = index + 1
                    else:
                        category = index + 2
                    category_found = True
                    categories.append(category)
                    break
                else:            
                    # When value equals the middle bound.
                    if middle_val_cat == 'lower':
                        category = index + 1
                    else:
                        category = index + 2
                    category_found = True
                    categories.append(category)
                    break
        if not category_found:
            # The value is above all boundaries.
            categories.append(index + 2)
    return categories

def category_probabilities(values, bounds, boundary_val_cat='outer', 
                              middle_val_cat='upper', return_counts=False):
    """
    Given a set of values and boundaries, return the associated probabilities 
    for each category. There are always 1 + number of bounds categories.
    
    Args:
    
    * values: list
        A list of values.
    
    * bounds: list
        A list of boundary values. These are automatically sorted into numeric 
        order.

    Kwargs:

    * boundary_val_cat:
        If a value equals a boundary value, specify whether it is placed in an 
        inner or outer category. Default is outer.
    
    * middle_val_cat:
        If a value equals the middle boundary value (only for odd number of 
        boundaries), specify whether it is placed in the upper or lower 
        category. Default is upper.

    Returns:
        list
    
    """
    category_counts = [0.] * (len(bounds) + 1)
    num_of_vals     = float(len(values))
    categories = value_category(values, bounds, boundary_val_cat, 
                                middle_val_cat)
    for category in categories:
        category_counts[category - 1] += 1
    
    if return_counts:
        return [int(val) for val in category_counts]
    else:
        category_probs = [val / num_of_vals for val in category_counts]
        return category_probs

def pdf_probabilities(pdf, bounds):
    """
    Calculate the area of the PDF in between each bound, hence the probability.

    Args:
    
    * pdf: instance of scipy.stats.gaussian_kde
    
    * bounds: list
        A list of boundary values. These are automatically sorted into numeric 
        order.

    """
    bounds.sort()
    extended_boundaries = [-numpy.inf] + bounds
    extended_boundaries.append(numpy.inf)
    probs = []
    for i in range(len(extended_boundaries) - 1):
        probs.append(pdf.integrate_box_1d(extended_boundaries[i], extended_boundaries[i+1]))
    return probs

def pdf_percentile_boundaries(pdf, num_of_categories, accuracy_factor=50):
    """
    Estimate the boundary values when splitting a PDF in to equally sized 
    areas.
    
    Args:
    
    * pdf: instance of scipy.stats.gaussian_kde
    
    * num_of_categories: integer
        The number of equally sized areas the PDF is split into.
    
    Kwargs:
    
    * accuracy_factor: integer
        The estimation is calculated using iteration, this value specifies how
        many values to split the PDF into and iterate over. Therefore, the
        higher the factor, the longer the calculation takes but the more 
        accurate the returned values. Default is 50.
    
    Returns:
        list of bounds
    
    """
    dmin = numpy.min(pdf.dataset)
    dmax = numpy.max(pdf.dataset)
    x_vals = numpy.linspace(dmin, dmax, accuracy_factor)
    
    required_area_size = 1. / float(num_of_categories)
    bounds = []
    lower_bound = -numpy.inf
    for i, x_val in enumerate(x_vals):        
        this_area_size = pdf.integrate_box_1d(lower_bound, x_val)
        if this_area_size > required_area_size:
            upper_diff = this_area_size - required_area_size
            lower_diff = required_area_size - \
                         pdf.integrate_box_1d(lower_bound, x_vals[i-1])
            total_diff = upper_diff + lower_diff
            proportion_diff = upper_diff / total_diff
            
            val_diff = x_val - x_vals[i-1]
            proportion_val_diff = val_diff * proportion_diff
            adjusted_x_val = x_val - proportion_val_diff
            bounds.append(adjusted_x_val)
            if len(bounds) == num_of_categories - 1:
                break
            lower_bound = adjusted_x_val
            
    return bounds

def calculate_pdf_limits(pdf, levels=50, range_limiter=20):
    """
    Calculate the values where the PDF stops. The range_limiter determines the 
    value at which to cut the PDF outer limits. It is a proportional value not 
    an actual value. The larger the given value the further out the extremes 
    will be returned.

    Args:
    
    * pdf: instance of scipy.stats.gaussian_kde

    Kwargs:
    
    * levels : integer
        This determines the step size when calculating the limits.
    
    * range_limiter: scalar
        This value is used to calculate the range of the PDF. A PDF function 
        can take a while to converge to 0, so to calculate sensible stop and 
        start points, some proportional value above 0 is calculated. The given
        range_limiter value is used as factor to determine what that above 0 
        value is. Simply, the higher the given value the wider the PDF limits.
        See nested function calculate_pdf_limits for more details.

    """
    dmin = numpy.min(pdf.dataset)
    dmax = numpy.max(pdf.dataset)
    pdf_min = numpy.mean([pdf(dmin)[0], pdf(dmax)[0]]) / float(range_limiter)
    # First calculate the appropriate step size given the data range and number
    # of levels.
    step_size = (dmax - dmin) / float(levels)
    while pdf(dmin)[0] > pdf_min:
        dmin -= step_size
    while pdf(dmax)[0] > pdf_min:
        dmax += step_size
    return dmin, dmax
