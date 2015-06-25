import numpy
from matplotlib.colors import LinearSegmentedColormap, ListedColormap

def colour_map(colours, match_colour=None, match_value=None, dmin=None, 
                dmax=None, data=None, cmap_len=256, extend='neither'):
    """
    Return a matplotlib colour map from a list of colours. A single colour 
    within the list can be assigned a value by providing the data limits that 
    the colour map will be used on. Note, if using this functionality, 
    match_colour, match_value and data limits (or all the data) must be 
    provided.
    
    Args:
    
    * colours: list
        A list of matplotlib accepted colours. These include names (see 
        http://www.w3schools.com/html/html_colornames.asp), html hex colour 
        codes and RGB arrays.
    
    Kwargs:
    
    * match_colour: string or RBG array
        Specify one of the colours in the colour list (but not the first or 
        last) to be matched against a given value (see below).
    
    * match_value: float
        Specify a value to which a given colour is to be matched.
    
    * dmin: float
        Data minimum.
    
    * dmax: 
        Data maximum
        
    * data: array like
        Alternative to providing the limits. Limits are calculated using the 
        data within the function.
    
    * cmap_len: integer
        Total number of colours in the colour map.
    
    * extend: 'neither' or 'both'
        If 'both', the first and last colours are set to under and over data
        range colours.
    
    Returns:
        matplotlib.colors.Colormap
    
    """
    cmap = LinearSegmentedColormap.from_list('cmap', colours, N=cmap_len)
    if match_colour is not None:       
        assert match_value is not None, 'A value must be given with which to '\
        'match the colour.'
        colours = [colour.lower() for colour in colours]
        match_colour = match_colour.lower()
        assert match_colour in colours, 'The colour to match, %s, is not in'\
        ' the given colours list, %s.' % (match_colour, colours)
        if dmin is None or dmax is None:
            assert data is not None, 'To scale the colour map, data or data '\
            'minimum and maximum must be provided.'
            dmin = numpy.min(data)
            dmax = numpy.max(data)
        else:
            assert dmin is not None and dmax is not None, 'Both dmin and dmax'\
            ' must be provided.'
            assert dmin < dmax, 'dmin must be smaller than dmax.'
        
        assert dmin <= match_value <= dmax, 'match_value, %s, value must fall'\
        ' within the data range, %s & %s.' % (match_value, dmin, dmax) 
                                      
        colour_position = float(colours.index(match_colour)) / \
                          float(len(colours) - 1)
        if colour_position in [0., 1]:
            raise UserWarning('The colour to match the value cannot be a '\
                              'colour on the limits of the colour map.')
        value_position = float(match_value - dmin) / \
                               float(dmax - dmin)
                               
        if value_position > colour_position:
            # Cut off the top end of the colour map using equation...
            x = (colour_position * cmap.N) / value_position
            # Take colours from 0 to x (+1 for range to reach x value)
            colour_RGBs = cmap(range(int(round(x + 1))))
            cmap = ListedColormap(colour_RGBs)
        elif value_position < colour_position:
            # Cut off the bottom end of the colour map using equation...
            x = ((colour_position - value_position) * cmap.N) / \
                 (1. - value_position)
            # Take colours from x to end colour index (+1 for range to reach x 
            # value)
            colour_RGBs = cmap(range(int(round(x)), (cmap.N + 1)))
            cmap = ListedColormap(colour_RGBs)
    else:
        assert match_value is None, 'A value has been specified without a '\
        'colour to match it with.'
    if extend == 'both':
        over_colour = cmap(cmap.N)
        under_colour = cmap(0)
        colour_RGBs = cmap(range(1, cmap.N - 1))
        cmap = ListedColormap(colour_RGBs)
        cmap.set_over(over_colour)
        cmap.set_under(under_colour)
        
    return cmap
