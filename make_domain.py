#######################################################
# Generate a new model domain.
#######################################################

import numpy as np
import sys

from constants import deg2rad
from io import write_binary, NCfile_basiclatlon
from utils import factors, polar_stereo
from interpolation import extend_into_mask, interp_topo, remove_isolated_cells
from plot_latlon import plot_tmp_domain

def latlon_points (xmin, xmax, ymin, ymax, res, dlat_file, prec=64):

    # Number of iterations for latitude convergence
    num_lat_iter = 10    

    # Build longitude values
    lon = np.arange(xmin, xmax+res, res)
    # Update xmax if the range doesn't evenly divide by res
    if xmax != lon[-1]:
        xmax = lon[-1]
        print 'Eastern boundary moved to ' + str(xmax)
    # Put xmin in the range (0, 360) for namelist
    if xmin < 0:
        xmin += 360

    # First guess for latitude: resolution scaled by latitude of southern edge
    lat = [ymin]
    while lat[-1] < ymax:
        lat.append(lat[-1] + res*np.cos(lat[-1]*deg2rad))
    lat = np.array(lat)
    # Now iterate to converge on resolution scaled by latitude of centres
    for iter in range(num_lat_iter):
        lat_old = np.copy(lat)
        # Latitude at centres    
        lat_c = 0.5*(lat[:-1] + lat[1:])
        j = 0
        lat = [ymin]
        while lat[-1] < ymax and j < lat_c.size:
            lat.append(lat[-1] + res*np.cos(lat_c[j]*deg2rad))
            j += 1
        lat = np.array(lat)
    # Update ymax
    ymax = lat[-1]
    print 'Northern boundary moved to ' + str(ymax)

    # Write latitude resolutions to file
    dlat = lat[1:] - lat[:-1]
    write_binary(dlat, dlat_file, prec=prec)

    # Remind the user what to do in their namelist
    print '\nChanges to make to input/data:'
    print 'xgOrigin=' + str(xmin)
    print 'ygOrigin=' + str(ymin)
    print 'dxSpacing=' + str(res)
    print "delYfile='" + dlat_file + "' (and copy this file into input/)"

    # Find dimensions of tracer grid
    Nx = lon.size-1
    Ny = lat.size-1
    # Find all the factors
    factors_x = factors(Nx)
    factors_y = factors(Ny)
    print '\nNx = ' + str(Nx) + ' which has the factors ' + str(factors_x)
    print 'Ny = ' + str(Ny) + ' which has the factors ' + str(factors_y)
    print 'If you are happy with this, proceed with interp_bedmap2. At some point, choose your tile size based on the factors and update code/SIZE.h.'
    print 'Otherwise, tweak the boundaries and try again.'

    return lon, lat


# Interpolate BEDMAP2 bathymetry, ice shelf draft, and masks to the new grid. Write the results to a NetCDF file so the user can check for any remaining artifacts that need fixing (eg blocking out the little islands near the peninsula).
def interp_bedmap2 (lon, lat, topo_dir, nc_out, seb_updates=True):

    # BEDMAP2 file names
    if seb_updates:
        bed_file = 'bedmap2_bed_seb.flt'
    else:
        bed_file = 'bedmap2_bed.flt'
    surface_file='bedmap2_surface.flt'
    thickness_file='bedmap2_thickness.flt'
    mask_file='bedmap2_icemask_grounded_and_shelves.flt'

    # BEDMAP2 grid parameters
    bedmap_dim = 6667    # Dimension
    bedmap_bdry = 3333000    # Polar stereographic coordinate (m) on boundary
    bedmap_res = 1000    # Resolution (m)
    missing_val = -9999    # Missing value for bathymetry north of 60S

    if np.amax(lat) > -60:
        print 'Error (interp_topo): BEDMAP2 has northern boundary 60S. You will need to edit the code to either merge in GEBCO, switch to RTopo, or something else.'
        sys.exit()

    # Set up BEDMAP grid (polar stereographic)
    x = np.arange(-bedmap_bdry, bedmap_bdry+bedmap_res, bedmap_res)
    y = np.arange(-bedmap_bdry, bedmap_bdry+bedmap_res, bedmap_res)

    print 'Reading data'
    # Have to flip it vertically so lon0=0 in polar stereographic projection
    # Otherwise, lon0=180 which makes x_interp and y_interp strictly decreasing when we call polar_stereo later, and the interpolation chokes
    bathy = np.flipud(np.fromfile(topo_dir+bed_file, dtype='<f4').reshape([bedmap_dim, bedmap_dim]))
    surf = np.flipud(np.fromfile(topo_dir+surface_file, dtype='<f4').reshape([bedmap_dim, bedmap_dim]))
    thick = np.flipud(np.fromfile(topo_dir+thickness_file, dtype='<f4').reshape([bedmap_dim, bedmap_dim]))
    mask = np.flipud(np.fromfile(topo_dir+mask_file, dtype='<f4').reshape([bedmap_dim, bedmap_dim]))

    print 'Extending bathymetry slightly past 60S'
    # Bathymetry has missing values north of 60S. Extend into that mask so there are no artifacts near 60S.
    bathy = extend_into_mask(bathy, missing_val=missing_val)

    print 'Calculating ice shelf draft'
    # Calculate ice shelf draft from ice surface and ice thickness
    draft = surf - thick

    print 'Calculating ocean and ice masks'
    # Mask: -9999 is open ocean, 0 is grounded ice, 1 is ice shelf
    # Make an ocean mask and an ice mask. Ice shelves are in both.
    omask = (mask!=0).astype(float)
    imask = (mask!=-9999).astype(float)

    # Convert lon and lat to polar stereographic coordinates
    lon_2d, lat_2d = np.meshgrid(lon, lat)
    x_interp, y_interp = polar_stereo(lon_2d, lat_2d)

    # Interpolate fields
    print 'Interpolating bathymetry'
    bathy_interp = interp_topo(x, y, bathy, x_interp, y_interp)
    print 'Interpolating ice shelf draft'
    draft_interp = interp_topo(x, y, draft, x_interp, y_interp)
    print 'Interpolating ocean mask'
    omask_interp = interp_topo(x, y, omask, x_interp, y_interp)
    print 'Interpolating ice mask'
    imask_interp = interp_topo(x, y, imask, x_interp, y_interp)

    print 'Processing masks'
    # Deal with values interpolated between 0 and 1
    omask_interp[omask_interp < 0.5] = 0
    omask_interp[omask_interp >= 0.5] = 1
    imask_interp[imask_interp < 0.5] = 0
    imask_interp[imask_interp >= 0.5] = 1
    # Zero out bathymetry and ice shelf draft on land    
    bathy_interp[omask_interp==0] = 0
    draft_interp[omask_interp==0] = 0
    # Zero out ice shelf draft in the open ocean
    draft_interp[imask_interp==0] = 0
    
    # Update masks due to interpolation changing their boundaries
    # Anything with positive bathymetry should be land
    index = bathy_interp > 0
    omask_interp[index] = 0
    bathy_interp[index] = 0
    draft_interp[index] = 0    
    # Anything with negative or zero water column thickness should be land
    index = draft_interp - bathy_interp <= 0
    omask_interp[index] = 0
    bathy_interp[index] = 0
    draft_interp[index] = 0
    # Any ocean points with zero ice shelf draft should not be in the ice mask
    index = np.nonzero((omask_interp==1)*(draft_interp==0))
    imask_interp[index] = 0

    print 'Removing isolated ocean cells'
    omask_interp = remove_isolated_cells(omask_interp)
    bathy_interp[omask_interp==0] = 0
    draft_interp[omask_interp==0] = 0
    print 'Removing isolated ice shelf cells'
    # First make a mask that is just ice shelves (no grounded ice)
    shelf_mask_interp = np.copy(imask_interp)
    shelf_mask_interp[omask_interp==0] = 0
    shelf_mask_interp = remove_isolated_cells(shelf_mask_interp)
    index = np.nonzero((omask_interp==1)*(shelf_mask_interp==0))
    draft_interp[index] = 0
    imask_interp[index] = 0

    print 'Plotting'
    plot_tmp_domain(lon_2d, lat_2d, bathy_interp, title='Bathymetry (m)')
    plot_tmp_domain(lon_2d, lat_2d, draft_interp, title='Ice shelf draft (m)')
    plot_tmp_domain(lon_2d, lat_2d, draft_interp - bathy_interp, title='Water column thickness (m)')
    plot_tmp_domain(lon_2d, lat_2d, omask_interp, title='Ocean mask')
    plot_tmp_domain(lon_2d, lat_2d, imask_interp, title='Ice mask')

    # Write to NetCDF file (at cell centres not edges!)
    ncfile = NCfile_basiclatlon(nc_out, 0.5*(lon[1:] + lon[:-1]), 0.5*(lat[1:] + lat[:-1]))
    ncfile.add_variable('bathy', bathy_interp, units='m')
    ncfile.add_variable('draft', draft_interp, units='m')
    ncfile.add_variable('omask', omask_interp)
    ncfile.add_variable('imask', imask_interp)
    ncfile.finished()

    print 'The results have been written into ' + nc_out
    print 'Take a look at this file and make whatever manual edits you would like (removing subglacial lakes, blocking out the annoying little islands near the peninsula, removing everything west of the peninsula...)'
    print 'Then run write_topo_files to generate the input topography files for the model.'
    
    

    