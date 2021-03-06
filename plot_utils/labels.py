#######################################################
# Create nice labels and axes for plots.
#######################################################

import matplotlib.dates as dt
import numpy as np
import sys

from ..file_io import netcdf_time
from ..constants import fris_bounds


# On a timeseries plot with axes ax, label every month (monthly_ticks) or every year (yearly_ticks)

def monthly_ticks (ax):

    ax.xaxis.set_major_locator(dt.MonthLocator())
    ax.xaxis.set_major_formatter(dt.DateFormatter("%b '%y"))

    
def yearly_ticks (ax):

    ax.xaxis.set_major_locator(dt.YearLocator())
    ax.xaxis.set_major_formatter(dt.DateFormatter('%Y'))


# Format the latitude or longitude x as a string, rounded to max_decimals (with no unnecessary trailing zeros), and expressed as a compass direction eg 30 <degrees> W instead of -30.
# latlon_label is the helper function, lon_label and lat_label are the APIs.

def latlon_label (x, suff_minus, suff_plus, max_decimals):

    # Figure out if it's south/west or north/east
    if x < 0:
        x = -x
        suff = suff_minus
    else:
        suff = suff_plus

    # Round to the correct number of decimals, with no unnecessary trailing 0s
    for d in range(max_decimals+1):
        if round(x,d) == x or d == max_decimals:
            fmt = '{0:.'+str(d)+'f}'
            label = fmt.format(round(x,d))
            break

    return label + suff


def lon_label (x, max_decimals):

    return latlon_label(x, r'$^{\circ}$W', r'$^{\circ}$E', max_decimals)


def lat_label (x, max_decimals):

    return latlon_label(x, r'$^{\circ}$S', r'$^{\circ}$N', max_decimals)


# Set the limits of the longitude and latitude axes (pass 1D or 2D arrays, doesn't matter), and give them nice labels.
# Setting zoom_fris=True will zoom into the FRIS cavity (bounds set in constants.py). You can also set specific limits on longitude and latitude (xmin etc.)
def latlon_axes (ax, lon, lat, zoom_fris=False, xmin=None, xmax=None, ymin=None, ymax=None):
    
    # Set limits on axes
    if zoom_fris:
        xmin = fris_bounds[0]
        xmax = fris_bounds[1]
        ymin = fris_bounds[2]
        ymax = fris_bounds[3]
    if xmin is None:
        xmin = np.amin(lon)
    if xmax is None:
        xmax = np.amax(lon)
    if ymin is None:
        ymin = np.amin(lat)
    if ymax is None:
        ymax = np.amax(lat)
    ax.set_xlim([xmin, xmax])
    ax.set_ylim([ymin, ymax])

    # Check location of ticks
    lon_ticks = ax.get_xticks()
    lat_ticks = ax.get_yticks()
    # Often there are way more longitude ticks than latitude ticks
    if float(len(lon_ticks))/float(len(lat_ticks)) > 1.5:
        # Automatic tick locations can disagree with limits of axes, but this doesn't change the axes limits unless you get and then set the tick locations. So make sure there are no disagreements now.
        lon_ticks = lon_ticks[(lon_ticks >= ax.get_xlim()[0])*(lon_ticks <= ax.get_xlim()[1])]
        # Remove every second one
        lon_ticks = lon_ticks[1::2]        
        ax.set_xticks(lon_ticks)

    # Set nice tick labels
    lon_labels = []
    for x in lon_ticks:
        lon_labels.append(lon_label(x,2))
    ax.set_xticklabels(lon_labels)
    # Repeat for latitude
    lat_labels = []
    for y in lat_ticks:
        lat_labels.append(lat_label(y,2))
    ax.set_yticklabels(lat_labels)


# Give the axes on a slice plot nice labels. Set h_axis to 'lat' (default) or 'lon' to indicate what the horizontal axis is.
def slice_axes (ax, h_axis='lat'):

    # Set horizontal tick labels
    h_ticks = ax.get_xticks()   
    h_labels = []
    for x in h_ticks:
        if h_axis == 'lat':
            h_labels.append(lat_label(x,2))
        elif h_axis == 'lon':
            h_labels.append(lon_label(x,2))
    ax.set_xticklabels(h_labels)

    # Set vertical tick labels
    z_ticks = ax.get_yticks()
    z_labels = []
    for z in z_ticks:
        # Will probably never have decimal places, so just format as a positive integer
        z_labels.append(str(int(round(-z))))
    ax.set_yticklabels(z_labels)
    ax.set_ylabel('Depth (m)', fontsize=14)


# Given a date, return a nice string that can be added to plots.
# Option 1: set keyword argument "date" with a Datetime object.
# Option 2: set keyword arguments "file_path" and "time_index" to read the date from a NetCDF file.
# The keyword argument "monthly" indicates that the output is monthly averaged.
def parse_date (date=None, file_path=None, time_index=None, monthly=True):

    # Create the Datetime object if needed
    if date is None:
        date = netcdf_time(file_path, monthly=monthly)[time_index]
    if monthly:
        # Return month and year
        return date.strftime('%b %Y')
    else:
        # Just go with the day that's in the timestamp, even though it's not representative of the averaging period
        return date.strftime('%d %b %Y')
