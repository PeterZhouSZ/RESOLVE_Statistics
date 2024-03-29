"""
{This script plots SMF and SMHM from results of the mcmc including best fit and
 68th percentile of lowest chi-squared values. This is compared to data and is
 done for all 3 surveys: ECO, RESOLVE-A and RESOLVE-B.}
"""

# Matplotlib backend
# import matplotlib
# matplotlib.use('Agg')

# Libs
from halotools.empirical_models import PrebuiltSubhaloModelFactory
from cosmo_utils.utils.stats_funcs import Stats_one_arr
from halotools.sim_manager import CachedHaloCatalog
from cosmo_utils.utils import work_paths as cwpaths
from collections import OrderedDict
from multiprocessing import Pool
import matplotlib.pyplot as plt
from matplotlib import rc
import pandas as pd
import numpy as np
import argparse
import random
import math
import time
import os

__author__ = '{Mehnaaz Asad}'

rc('font', **{'family': 'sans-serif', 'sans-serif': ['Helvetica']}, size=20)
rc('text', usetex=True)
rc('text.latex', preamble=[r"\usepackage{amsmath}"])

def read_chi2(path_to_file):
    """
    Reads chi-squared values from file

    Parameters
    ----------
    path_to_file: string
        Path to chi-squared values file

    Returns
    ---------
    chi2: array
        Array of reshaped chi^2 values to match chain values
    """
    chi2_df = pd.read_csv(path_to_file,header=None,names=['chisquared'])

    if mf_type == 'smf' and survey == 'eco':
        # Needed to reshape since flattened along wrong axis, 
        # didn't correspond to chain
        test_reshape = chi2_df.chisquared.values.reshape((1000,250))
        chi2 = np.ndarray.flatten(np.array(test_reshape),'F')
    
    else:
        chi2 = chi2_df.chisquared.values

    return chi2

def read_mcmc(path_to_file):
    """
    Reads mcmc chain from file

    Parameters
    ----------
    path_to_file: string
        Path to mcmc chain file

    Returns
    ---------
    emcee_table: pandas dataframe
        Dataframe of mcmc chain values with NANs removed
    """
    colnames = ['mhalo_c','mstellar_c','lowmass_slope','highmass_slope',\
        'scatter']
    
    if mf_type == 'smf' and survey == 'eco':
        emcee_table = pd.read_csv(path_to_file,names=colnames,sep='\s+',\
            dtype=np.float64)

    else:
        emcee_table = pd.read_csv(path_to_file, names=colnames, 
            delim_whitespace=True, header=None)

        emcee_table = emcee_table[emcee_table.mhalo_c.values != '#']
        emcee_table.mhalo_c = emcee_table.mhalo_c.astype(np.float64)
        emcee_table.mstellar_c = emcee_table.mstellar_c.astype(np.float64)
        emcee_table.lowmass_slope = emcee_table.lowmass_slope.astype(np.float64)

    # Cases where last parameter was a NaN and its value was being written to 
    # the first element of the next line followed by 4 NaNs for the other 
    # parameters
    for idx,row in enumerate(emcee_table.values):
        if np.isnan(row)[4] == True and np.isnan(row)[3] == False:
            scatter_val = emcee_table.values[idx+1][0]
            row[4] = scatter_val
    
    # Cases where rows of NANs appear
    emcee_table = emcee_table.dropna(axis='index', how='any').\
        reset_index(drop=True)
    
    return emcee_table

def read_data_catl(path_to_file, survey):
    """
    Reads survey catalog from file

    Parameters
    ----------
    path_to_file: `string`
        Path to survey catalog file

    survey: `string`
        Name of survey

    Returns
    ---------
    catl: `pandas.DataFrame`
        Survey catalog with grpcz, abs rmag and stellar mass limits
    
    volume: `float`
        Volume of survey

    cvar: `float`
        Cosmic variance of survey

    z_median: `float`
        Median redshift of survey
    """
    if survey == 'eco':
        # 13878 galaxies
        eco_buff = pd.read_csv(path_to_file,delimiter=",", header=0)

        if mf_type == 'smf':
            # 6456 galaxies                       
            catl = eco_buff.loc[(eco_buff.grpcz.values >= 3000) & 
                (eco_buff.grpcz.values <= 7000) & 
                (eco_buff.absrmag.values <= -17.33) &
                (eco_buff.logmstar.values >= 8.9)]
        elif mf_type == 'bmf':
            catl = eco_buff.loc[(eco_buff.grpcz.values >= 3000) & 
                (eco_buff.grpcz.values <= 7000) & 
                (eco_buff.absrmag.values <= -17.33)] 

        volume = 151829.26 # Survey volume without buffer [Mpc/h]^3
        cvar = 0.125
        z_median = np.median(catl.grpcz.values) / (3 * 10**5)
        
    elif survey == 'resolvea' or survey == 'resolveb':
        # 2286 galaxies
        resolve_live18 = pd.read_csv(path_to_file, delimiter=",", header=0)

        if survey == 'resolvea':
            if mf_type == 'smf':
                catl = resolve_live18.loc[
                    (resolve_live18.grpcz.values >= 4500) & 
                    (resolve_live18.grpcz.values <= 7000) & 
                    (resolve_live18.absrmag.values <= -17.33) & 
                    (resolve_live18.logmstar.values >= 8.9)]
                # catl = resolve_live18.loc[(resolve_live18.f_a.values == 1) & 
                #     (resolve_live18.grpcz.values >= 4500) & 
                #     (resolve_live18.grpcz.values <= 7000) & 
                #     (resolve_live18.absrmag.values <= -17.33) & 
                #     (resolve_live18.logmstar.values >= 8.9)]
            elif mf_type == 'bmf':
                catl = resolve_live18.loc[(resolve_live18.f_a.values == 1) & 
                    (resolve_live18.grpcz.values >= 4500) & 
                    (resolve_live18.grpcz.values <= 7000) & 
                    (resolve_live18.absrmag.values <= -17.33)]

            volume = 13172.384  # Survey volume without buffer [Mpc/h]^3
            cvar = 0.30
            z_median = np.median(resolve_live18.grpcz.values) / (3 * 10**5)
        
        elif survey == 'resolveb':
            if mf_type == 'smf':
                # 487 - cz, 369 - grpcz
                catl = resolve_live18.loc[(resolve_live18.f_b.values == 1) & 
                    (resolve_live18.grpcz.values >= 4500) & 
                    (resolve_live18.grpcz.values <= 7000) & 
                    (resolve_live18.absrmag.values <= -17) & 
                    (resolve_live18.logmstar.values >= 8.7)]
            elif mf_type == 'bmf':
                catl = resolve_live18.loc[(resolve_live18.f_b.values == 1) & 
                    (resolve_live18.grpcz.values >= 4500) & 
                    (resolve_live18.grpcz.values <= 7000) & 
                    (resolve_live18.absrmag.values <= -17)]

            volume = 4709.8373  # *2.915 #Survey volume without buffer [Mpc/h]^3
            cvar = 0.58
            z_median = np.median(resolve_live18.grpcz.values) / (3 * 10**5)

    return catl,volume,cvar,z_median

def read_mock_catl(filename, catl_format='.hdf5'):
    """
    Function to read ECO/RESOLVE catalogues.

    Parameters
    ----------
    filename: string
        path and name of the ECO/RESOLVE catalogue to read

    catl_format: string, optional (default = '.hdf5')
        type of file to read.
        Options:
            - '.hdf5': Reads in a catalogue in HDF5 format

    Returns
    -------
    mock_pd: pandas DataFrame
        DataFrame with galaxy/group information

    Examples
    --------
    # Specifying `filename`
    >>> filename = 'ECO_catl.hdf5'

    # Reading in Catalogue
    >>> mock_pd = reading_catls(filename, format='.hdf5')

    >>> mock_pd.head()
               x          y         z          vx          vy          vz  \
    0  10.225435  24.778214  3.148386  356.112457 -318.894409  366.721832
    1  20.945772  14.500367 -0.237940  168.731766   37.558834  447.436951
    2  21.335835  14.808488  0.004653  967.204407 -701.556763 -388.055115
    3  11.102760  21.782235  2.947002  611.646484 -179.032089  113.388794
    4  13.217764  21.214905  2.113904  120.689598  -63.448833  400.766541

       loghalom  cs_flag  haloid  halo_ngal    ...        cz_nodist      vel_tot  \
    0    12.170        1  196005          1    ...      2704.599189   602.490355
    1    11.079        1  197110          1    ...      2552.681697   479.667489
    2    11.339        1  197131          1    ...      2602.377466  1256.285409
    3    11.529        1  199056          1    ...      2467.277182   647.318259
    4    10.642        1  199118          1    ...      2513.381124   423.326770

           vel_tan     vel_pec     ra_orig  groupid    M_group g_ngal  g_galtype  \
    0   591.399858 -115.068833  215.025116        0  11.702527      1          1
    1   453.617221  155.924074  182.144134        1  11.524787      4          0
    2  1192.742240  394.485714  182.213220        1  11.524787      4          0
    3   633.928896  130.977416  210.441320        2  11.502205      1          1
    4   421.064495   43.706352  205.525386        3  10.899680      1          1

       halo_rvir
    0   0.184839
    1   0.079997
    2   0.097636
    3   0.113011
    4   0.057210
    """
    ## Checking if file exists
    if not os.path.exists(filename):
        msg = '`filename`: {0} NOT FOUND! Exiting..'.format(filename)
        raise ValueError(msg)
    ## Reading file
    if catl_format=='.hdf5':
        mock_pd = pd.read_hdf(filename)
    else:
        msg = '`catl_format` ({0}) not supported! Exiting...'.format(catl_format)
        raise ValueError(msg)

    return mock_pd

def get_paramvals_percentile(mcmc_table, pctl, chi2):
    """
    Isolates 68th percentile lowest chi^2 values and takes random 1000 sample

    Parameters
    ----------
    mcmc_table: pandas dataframe
        Mcmc chain dataframe

    pctl: int
        Percentile to use

    chi2: array
        Array of chi^2 values

    Returns
    ---------
    mcmc_table_pctl: pandas dataframe
        Sample of 100 68th percentile lowest chi^2 values
    """ 
    pctl = pctl/100
    mcmc_table['chi2'] = chi2
    mcmc_table = mcmc_table.sort_values('chi2').reset_index(drop=True)
    slice_end = int(pctl*len(mcmc_table))
    mcmc_table_pctl = mcmc_table[:slice_end]
    # Best fit params are the parameters that correspond to the smallest chi2
    bf_params = mcmc_table_pctl.drop_duplicates().reset_index(drop=True).\
        values[0][:5]
    bf_chi2 = mcmc_table_pctl.drop_duplicates().reset_index(drop=True).\
        values[0][5]
    # Randomly sample 100 lowest chi2 
    mcmc_table_pctl = mcmc_table_pctl.drop_duplicates().sample(100)

    return mcmc_table_pctl, bf_params, bf_chi2

def calc_bary(logmstar_arr, logmgas_arr):
    """Calculates baryonic mass of galaxies from survey"""
    logmbary = np.log10((10**logmstar_arr) + (10**logmgas_arr))
    return logmbary

def diff_smf(mstar_arr, volume, h1_bool):
    """
    Calculates differential stellar mass function

    Parameters
    ----------
    mstar_arr: numpy array
        Array of stellar masses

    volume: float
        Volume of survey or simulation

    h1_bool: boolean
        True if units of masses are h=1, False if units of masses are not h=1

    Returns
    ---------
    maxis: array
        Array of x-axis mass values

    phi: array
        Array of y-axis values

    err_tot: array
        Array of error values per bin
    
    bins: array
        Array of bin edge values
    """
    if not h1_bool:
        # changing from h=0.7 to h=1 assuming h^-2 dependence
        logmstar_arr = np.log10((10**mstar_arr) / 2.041)
    else:
        logmstar_arr = np.log10(mstar_arr)
    if survey == 'eco' or survey == 'resolvea':
        bin_min = np.round(np.log10((10**8.9) / 2.041), 1)
        if survey == 'eco':
            bin_max = np.round(np.log10((10**11.8) / 2.041), 1)
        elif survey == 'resolvea':
            # different to avoid nan in inverse corr mat
            bin_max = np.round(np.log10((10**11.5) / 2.041), 1)
        bins = np.linspace(bin_min, bin_max, 7)
    elif survey == 'resolveb':
        bin_min = np.round(np.log10((10**8.7) / 2.041), 1)
        bin_max = np.round(np.log10((10**11.8) / 2.041), 1)
        bins = np.linspace(bin_min, bin_max, 7) 
    # Unnormalized histogram and bin edges
    counts, edg = np.histogram(logmstar_arr, bins=bins)  # paper used 17 bins
    dm = edg[1] - edg[0]  # Bin width
    maxis = 0.5 * (edg[1:] + edg[:-1])  # Mass axis i.e. bin centers
    # Normalized to volume and bin width
    err_poiss = np.sqrt(counts) / (volume * dm)
    err_tot = err_poiss

    phi = counts / (volume * dm)  # not a log quantity
    phi = np.log10(phi)

    return maxis, phi, err_tot, bins, counts

def diff_bmf(mass_arr, volume, h1_bool):
    """
    Calculates differential baryonic mass function

    Parameters
    ----------
    mstar_arr: numpy array
        Array of baryonic masses

    volume: float
        Volume of survey or simulation

    cvar_err: float
        Cosmic variance of survey

    sim_bool: boolean
        True if masses are from mock

    Returns
    ---------
    maxis: array
        Array of x-axis mass values

    phi: array
        Array of y-axis values

    err_tot: array
        Array of error values per bin
    
    bins: array
        Array of bin edge values
    """
    if not h1_bool:
        # changing from h=0.7 to h=1 assuming h^-2 dependence
        logmbary_arr = np.log10((10**mass_arr) / 2.041)
        # print("Data ", logmbary_arr.min(), logmbary_arr.max())
    else:
        logmbary_arr = np.log10(mass_arr)
        # print(logmbary_arr.min(), logmbary_arr.max())
    if survey == 'eco' or survey == 'resolvea':
        bin_min = np.round(np.log10((10**9.4) / 2.041), 1)
        if survey == 'eco':
            bin_max = np.round(np.log10((10**11.8) / 2.041), 1)
        elif survey == 'resolvea':
            bin_max = np.round(np.log10((10**11.5) / 2.041), 1)
        bins = np.linspace(bin_min, bin_max, 7)
    elif survey == 'resolveb':
        bin_min = np.round(np.log10((10**9.1) / 2.041), 1)
        bin_max = np.round(np.log10((10**11.5) / 2.041), 1)
        bins = np.linspace(bin_min, bin_max, 7)
    # Unnormalized histogram and bin edges
    counts, edg = np.histogram(logmbary_arr, bins=bins)  # paper used 17 bins
    dm = edg[1] - edg[0]  # Bin width
    maxis = 0.5 * (edg[1:] + edg[:-1])  # Mass axis i.e. bin centers
    # Normalized to volume and bin width
    err_poiss = np.sqrt(counts) / (volume * dm)
    err_tot = err_poiss

    phi = counts / (volume * dm)  # not a log quantity
    phi = np.log10(phi)

    return maxis, phi, err_tot, bins, counts

def get_centrals_mock(gals_df):
    """
    Get centrals from mock catalog

    Parameters
    ----------
    gals_df: pandas dataframe
        Mock catalog

    Returns
    ---------
    cen_gals: array
        Array of central galaxy masses

    cen_halos: array
        Array of central halo masses
    """
    C_S = []
    for idx in range(len(gals_df)):
        if gals_df['halo_hostid'][idx] == gals_df['halo_id'][idx]:
            C_S.append(1)
        else:
            C_S.append(0)
    
    C_S = np.array(C_S)
    gals_df['C_S'] = C_S
    cen_gals = []
    cen_halos = []

    for idx,value in enumerate(gals_df['C_S']):
        if value == 1:
            cen_gals.append(gals_df['stellar_mass'][idx])
            cen_halos.append(gals_df['halo_mvir'][idx])

    cen_gals = np.log10(np.array(cen_gals))
    cen_halos = np.log10(np.array(cen_halos))

    return cen_gals, cen_halos

def get_centrals_data(catl):
    """
    Get centrals from survey catalog

    Parameters
    ----------
    catl: pandas dataframe
        Survey catalog

    Returns
    ---------
    cen_gals: array
        Array of central galaxy masses

    cen_halos: array
        Array of central halo masses
    """ 
    # cen_gals = []
    # cen_halos = []
    # for idx,val in enumerate(catl.fc.values):
    #     if val == 1:
    #         stellar_mass_h07 = catl.logmstar.values[idx]
    #         stellar_mass_h1 = np.log10((10**stellar_mass_h07) / 2.041)
    #         halo_mass_h07 = catl.logmh_s.values[idx]
    #         halo_mass_h1 = np.log10((10**halo_mass_h07) / 2.041)
    #         cen_gals.append(stellar_mass_h1)
    #         cen_halos.append(halo_mass_h1)
    
    if mf_type == 'smf':
        cen_gals = np.log10(10**catl.logmstar.loc[catl.fc.values == 1]/2.041)
        cen_halos = np.log10(10**catl.groupmass_s.loc[catl.fc.values == 1]/2.041)
    elif mf_type == 'bmf':
        logmstar = catl.logmstar.loc[catl.fc.values == 1]
        logmgas = catl.logmgas.loc[catl.fc.values == 1]
        logmbary = calc_bary(logmstar, logmgas)
        catl['logmbary'] = logmbary
        if survey == 'eco' or survey == 'resolvea':
            limit = 9.4
        elif survey == 'resolveb':
            limit = 9.1
        cen_gals = np.log10((10**(catl.logmbary.loc[(catl.fc.values == 1) & 
            (catl.logmbary.values >= limit)]))/2.041)
        cen_halos = np.log10((10**(catl.logmh_s.loc[(catl.fc.values == 1) & 
            (catl.logmbary.values >= limit)]))/2.041)

    return cen_gals, cen_halos

def halocat_init(halo_catalog,z_median):
    """
    Initial population of halo catalog using populate_mock function

    Parameters
    ----------
    halo_catalog: string
        Path to halo catalog
    
    z_median: float
        Median redshift of survey

    Returns
    ---------
    model: halotools model instance
        Model based on behroozi 2010 SMHM
    """
    halocat = CachedHaloCatalog(fname=halo_catalog, update_cached_fname=True)
    model = PrebuiltSubhaloModelFactory('behroozi10', redshift=z_median, \
        prim_haloprop_key='halo_macc')
    model.populate_mock(halocat,seed=5)

    return model

def populate_mock(theta):
    """
    Populate mock based on five parameter values 

    Parameters
    ----------
    theta: array
        Array of parameter values

    Returns
    ---------
    gals_df: pandas dataframe
        Dataframe of mock catalog
    """
    mhalo_characteristic, mstellar_characteristic, mlow_slope, mhigh_slope,\
        mstellar_scatter = theta
    model_init.param_dict['smhm_m1_0'] = mhalo_characteristic
    model_init.param_dict['smhm_m0_0'] = mstellar_characteristic
    model_init.param_dict['smhm_beta_0'] = mlow_slope
    model_init.param_dict['smhm_delta_0'] = mhigh_slope
    model_init.param_dict['scatter_model_param1'] = mstellar_scatter

    model_init.mock.populate()

    if survey == 'eco' or survey == 'resolvea':
        if mf_type == 'smf':
            limit = np.round(np.log10((10**8.9) / 2.041), 1)
        elif mf_type == 'bmf':
            limit = np.round(np.log10((10**9.4) / 2.041), 1)
    elif survey == 'resolveb':
        if mf_type == 'smf':
            limit = np.round(np.log10((10**8.7) / 2.041), 1)
        elif mf_type == 'bmf':
            limit = np.round(np.log10((10**9.1) / 2.041), 1)
    sample_mask = model_init.mock.galaxy_table['stellar_mass'] >= 10**limit
    gals = model_init.mock.galaxy_table[sample_mask]
    gals_df = gals.to_pandas()

    return gals_df

def mp_func(a_list):
    """
    Populate mock based on five parameter values

    Parameters
    ----------
    a_list: multidimensional array
        Array of five parameter values

    Returns
    ---------
    max_model_arr: array
        Array of x-axis mass values

    phi_model_arr: array
        Array of y-axis values

    err_tot_model_arr: array
        Array of error values per bin

    cen_gals_arr: array
        Array of central galaxy masses

    cen_halos_arr: array
        Array of central halo masses
    """
    v_sim = 130**3

    maxis_arr = []
    phi_arr = []
    err_tot_arr = []
    cen_gals_arr = []
    cen_halos_arr = []

    for theta in a_list:  
        gals_df = populate_mock(theta)
        mstellar_mock = gals_df.stellar_mass.values 
        if mf_type == 'smf':
            maxis, phi, err_tot, bins, counts = diff_smf(mstellar_mock, v_sim, 
                True)
        elif mf_type == 'bmf':
            maxis, phi, err_tot, bins, counts = diff_bmf(mstellar_mock, v_sim, 
                True)
        cen_gals, cen_halos = get_centrals_mock(gals_df)

        maxis_arr.append(maxis)
        phi_arr.append(phi)
        err_tot_arr.append(err_tot)
        cen_gals_arr.append(cen_gals)
        cen_halos_arr.append(cen_halos)

    return [maxis_arr, phi_arr, err_tot_arr, cen_gals_arr, cen_halos_arr]

def mp_init(mcmc_table_pctl,nproc):
    """
    Initializes multiprocessing of mocks and smf and smhm measurements

    Parameters
    ----------
    mcmc_table_pctl: pandas dataframe
        Mcmc chain dataframe of 1000 random samples

    nproc: int
        Number of processes to use in multiprocessing

    Returns
    ---------
    result: multidimensional array
        Array of smf and smhm data
    """
    start = time.time()
    chunks = np.array([mcmc_table_pctl.iloc[:,:5].values[i::5] \
        for i in range(5)])
    pool = Pool(processes=nproc)
    result = pool.map(mp_func, chunks)
    end = time.time()
    multi_time = end - start
    print("Multiprocessing took {0:.1f} seconds".format(multi_time))

    return result

def get_best_fit_model(best_fit_params):
    """
    Get SMF and SMHM information of best fit model given a survey

    Parameters
    ----------
    survey: string
        Name of survey

    Returns
    ---------
    max_model: array
        Array of x-axis mass values

    phi_model: array
        Array of y-axis values

    err_tot_model: array
        Array of error values per bin

    cen_gals: array
        Array of central galaxy masses

    cen_halos: array
        Array of central halo masses
    """   
    v_sim = 130**3
    gals_df = populate_mock(best_fit_params)
    mstellar_mock = gals_df.stellar_mass.values  # Read stellar masses

    if mf_type == 'smf':
        max_model, phi_model, err_tot_model, bins_model, counts_model =\
            diff_smf(mstellar_mock, v_sim, True)
    elif mf_type == 'bmf':
        max_model, phi_model, err_tot_model, bins_model, counts_model =\
            diff_bmf(mstellar_mock, v_sim, True)
    cen_gals, cen_halos = get_centrals_mock(gals_df)

    return max_model, phi_model, err_tot_model, counts_model, cen_gals, \
        cen_halos

def jackknife(catl, volume):
    """
    Jackknife survey to get data in error and correlation matrix for 
    chi-squared calculation

    Parameters
    ----------
    catl: Pandas DataFrame
        Survey catalog

    Returns
    ---------
    stddev_jk: numpy array
        Array of sigmas
    corr_mat_inv: numpy matrix
        Inverse of correlation matrix
    """

    ra = catl.radeg.values # degrees
    dec = catl.dedeg.values # degrees

    sin_dec_all = np.rad2deg(np.sin(np.deg2rad(dec))) # degrees

    sin_dec_arr = np.linspace(sin_dec_all.min(), sin_dec_all.max(), 11)
    ra_arr = np.linspace(ra.min(), ra.max(), 11)

    grid_id_arr = []
    gal_id_arr = []
    grid_id = 1
    max_bin_id = len(sin_dec_arr)-2 # left edge of max bin
    for dec_idx in range(len(sin_dec_arr)):
        for ra_idx in range(len(ra_arr)):
            try:
                if dec_idx == max_bin_id and ra_idx == max_bin_id:
                    catl_subset = catl.loc[(catl.radeg.values >= ra_arr[ra_idx]) &
                        (catl.radeg.values <= ra_arr[ra_idx+1]) & 
                        (np.rad2deg(np.sin(np.deg2rad(catl.dedeg.values))) >= 
                            sin_dec_arr[dec_idx]) & (np.rad2deg(np.sin(np.deg2rad(
                                catl.dedeg.values))) <= sin_dec_arr[dec_idx+1])] 
                elif dec_idx == max_bin_id:
                    catl_subset = catl.loc[(catl.radeg.values >= ra_arr[ra_idx]) &
                        (catl.radeg.values < ra_arr[ra_idx+1]) & 
                        (np.rad2deg(np.sin(np.deg2rad(catl.dedeg.values))) >= 
                            sin_dec_arr[dec_idx]) & (np.rad2deg(np.sin(np.deg2rad(
                                catl.dedeg.values))) <= sin_dec_arr[dec_idx+1])] 
                elif ra_idx == max_bin_id:
                    catl_subset = catl.loc[(catl.radeg.values >= ra_arr[ra_idx]) &
                        (catl.radeg.values <= ra_arr[ra_idx+1]) & 
                        (np.rad2deg(np.sin(np.deg2rad(catl.dedeg.values))) >= 
                            sin_dec_arr[dec_idx]) & (np.rad2deg(np.sin(np.deg2rad(
                                catl.dedeg.values))) < sin_dec_arr[dec_idx+1])] 
                else:                
                    catl_subset = catl.loc[(catl.radeg.values >= ra_arr[ra_idx]) &
                        (catl.radeg.values < ra_arr[ra_idx+1]) & 
                        (np.rad2deg(np.sin(np.deg2rad(catl.dedeg.values))) >= 
                            sin_dec_arr[dec_idx]) & (np.rad2deg(np.sin(np.deg2rad(
                                catl.dedeg.values))) < sin_dec_arr[dec_idx+1])] 
                # Append dec and sin  
                for gal_id in catl_subset.name.values:
                    gal_id_arr.append(gal_id)
                for grid_id in [grid_id] * len(catl_subset):
                    grid_id_arr.append(grid_id)
                grid_id += 1
            except IndexError:
                break

    gal_grid_id_data = {'grid_id': grid_id_arr, 'name': gal_id_arr}
    df_gal_grid = pd.DataFrame(data=gal_grid_id_data)

    catl = catl.join(df_gal_grid.set_index('name'), on='name')
    catl = catl.reset_index(drop=True)

    # Loop over all sub grids, remove one and measure global smf
    jackknife_phi_arr = []
    for grid_id in range(len(np.unique(catl.grid_id.values))):
        grid_id += 1
        catl_subset = catl.loc[catl.grid_id.values != grid_id]  
        logmstar = catl_subset.logmstar.values
        logmgas = catl_subset.logmgas.values
        logmbary = calc_bary(logmstar, logmgas)
        if mf_type == 'smf':
            maxis, phi, err, bins, counts = diff_smf(logmstar, volume, False)
        elif mf_type == 'bmf':
            maxis, phi, err, bins, counts = diff_bmf(logmbary, volume, False)
        jackknife_phi_arr.append(phi)

    jackknife_phi_arr = np.array(jackknife_phi_arr)

    N = len(jackknife_phi_arr)

    # Covariance matrix
    cov_mat_xmf = np.cov(jackknife_phi_arr.T, bias=True)*(N-1)
    stddev_jk_xmf = np.sqrt(cov_mat_xmf.diagonal())

    jackknife_mass_arr = []
    for grid_id in range(len(np.unique(catl.grid_id.values))):
        grid_id += 1
        catl_subset = catl.loc[catl.grid_id.values != grid_id]  

        if mf_type == 'smf':
            # Both masses below in h=1.0
            cen_gal_mass, cen_halo_mass = get_centrals_data(catl_subset)
            x_smhm,y_smhm,y_std_smhm,y_std_err_smhm = \
                Stats_one_arr(cen_halo_mass, cen_gal_mass, base=0.4, 
                bin_statval='center')
            # Case where one set of measurements of mean stellar mass was one 
            # element smaller than the rest of the sets
            if survey == 'resolvea':
                if len(y_smhm) != 8:
                    y_smhm = np.append(y_smhm, 11.320157)
            jackknife_mass_arr.append(y_smhm)

        elif mf_type == 'bmf':
            # Both masses below in h=1.0
            cen_bary_mass, cen_halo_mass = get_centrals_data(catl_subset)
            x_bmhm,y_bmhm,y_std_bmhm,y_std_err_bmhm = \
                Stats_one_arr(cen_halo_mass, cen_bary_mass, base=0.4, 
                bin_statval='center')
            jackknife_mass_arr.append(y_bmhm)

    jackknife_mass_arr = np.array(jackknife_mass_arr)

    N = len(jackknife_mass_arr)

    # Covariance matrix
    cov_mat_xmhm = np.cov(jackknife_mass_arr.T, bias=True)*(N-1)
    stddev_jk_xmhm = np.sqrt(cov_mat_xmhm.diagonal())

    return stddev_jk_xmf, stddev_jk_xmhm

def get_xmhm_mocks(survey, path, mf_type):
    """
    Calculate error in data SMF from mocks

    Parameters
    ----------
    survey: string
        Name of survey
    path: string
        Path to mock catalogs

    Returns
    ---------
    err_total: array
        Standard deviation of phi values between samples of 8 mocks
    """

    if survey == 'eco':
        mock_name = 'ECO'
        num_mocks = 8
        min_cz = 3000
        max_cz = 7000
        mag_limit = -17.33
        mstar_limit = 8.9
        volume = 151829.26 # Survey volume without buffer [Mpc/h]^3
    elif survey == 'resolvea':
        mock_name = 'A'
        num_mocks = 59
        min_cz = 4500
        max_cz = 7000
        mag_limit = -17.33
        mstar_limit = 8.9
        volume = 13172.384  # Survey volume without buffer [Mpc/h]^3 
    elif survey == 'resolveb':
        mock_name = 'B'
        num_mocks = 104
        min_cz = 4500
        max_cz = 7000
        mag_limit = -17
        mstar_limit = 8.7
        volume = 4709.8373  # Survey volume without buffer [Mpc/h]^3


    x_arr = []
    y_arr = []
    y_std_err_arr = []
    for num in range(num_mocks):
        filename = path + '{0}_cat_{1}_Planck_memb_cat.hdf5'.format(
            mock_name, num)
        mock_pd = read_mock_catl(filename) 

        # Using the same survey definition as in mcmc smf i.e excluding the 
        # buffer
        if mf_type == 'smf':
            mock_pd = mock_pd.loc[(mock_pd.cz.values >= min_cz) & \
                (mock_pd.cz.values <= max_cz) & \
                (mock_pd.M_r.values <= mag_limit) & \
                (mock_pd.logmstar.values >= mstar_limit)]
            cen_gals = np.log10(10**(mock_pd.logmstar.loc
                [mock_pd.cs_flag == 1])/2.041)
            cen_halos = mock_pd.M_group.loc[mock_pd.cs_flag == 1]

            x,y,y_std,y_std_err = Stats_one_arr(cen_halos, cen_gals, base=0.4,
                bin_statval='center')

        elif mf_type == 'bmf':
            mock_pd = mock_pd.loc[(mock_pd.cz.values >= min_cz) & \
                (mock_pd.cz.values <= max_cz) & \
                (mock_pd.M_r.values <= mag_limit)]
            cen_gals_stellar = np.log10(10**(mock_pd.logmstar.loc
                [mock_pd.cs_flag == 1])/2.041)
            cen_gals_gas = mock_pd.mhi.loc[mock_pd.cs_flag == 1]
            cen_gals_gas = np.log10((1.4 * cen_gals_gas)/2.041)
            cen_gals_bary = calc_bary(cen_gals_stellar, cen_gals_gas)
            mock_pd['cen_gals_bary'] = cen_gals_bary
            if survey == 'eco' or survey == 'resolvea':
                limit = np.log10((10**9.4) / 2.041)
                cen_gals_bary = mock_pd.cen_gals_bary.loc\
                    [mock_pd.cen_gals_bary >= limit]
                cen_halos = mock_pd.M_group.loc[(mock_pd.cs_flag == 1) & 
                    (mock_pd.cen_gals_bary >= limit)]
            elif survey == 'resolveb':
                limit = np.log10((10**9.1) / 2.041)
                cen_gals_bary = mock_pd.cen_gals_bary.loc\
                    [mock_pd.cen_gals_bary >= limit]
                cen_halos = mock_pd.M_group.loc[(mock_pd.cs_flag == 1) & 
                    (mock_pd.cen_gals_bary >= limit)]

            x,y,y_std,y_std_err = Stats_one_arr(cen_halos, cen_gals_bary, 
                base=0.4, bin_statval='center')        

        x_arr.append(x)
        y_arr.append(y)
        y_std_err_arr.append(y_std_err)

    x_arr = np.array(x_arr)
    y_arr = np.array(y_arr)
    y_std_err_arr = np.array(y_std_err_arr)

    return [x_arr, y_arr, y_std_err_arr]

def plot_mf(result, max_model_bf, phi_model_bf, err_tot_model_bf, maxis_data, 
    phi_data, err_data, bf_chi2):
    """
    Plot SMF from data, best fit param values and param values corresponding to 
    68th percentile 1000 lowest chi^2 values

    Parameters
    ----------
    result: multidimensional array
        Array of SMF and SMHM information
    
    max_model_bf: array
        Array of x-axis mass values for best fit SMF

    phi_model_bf: array
        Array of y-axis values for best fit SMF
    
    err_tot_model_bf: array
        Array of error values per bin of best fit SMF

    maxis_data: array
        Array of x-axis mass values for data SMF

    phi_data: array
        Array of y-axis values for data SMF

    err_data: array
        Array of error values per bin of data SMF

    Returns
    ---------
    Nothing; SMF plot is saved in figures repository
    """
    if survey == 'resolvea':
        line_label = 'RESOLVE-A'
    elif survey == 'resolveb':
        line_label = 'RESOLVE-B'
    elif survey == 'eco':
        line_label = 'ECO'

    fig1 = plt.figure(figsize=(10,10))

    # lower_err = np.log10(phi_data - err_data)
    # upper_err = np.log10(phi_data + err_data)
    # lower_err = np.log10(phi_data) - lower_err
    # upper_err = upper_err - np.log10(phi_data)
    # asymmetric_err = [lower_err, upper_err]
    lower_err = phi_data - err_data
    upper_err = phi_data + err_data
    lower_err = phi_data - lower_err
    upper_err = upper_err - phi_data
    asymmetric_err = [lower_err, upper_err]
    plt.errorbar(maxis_data,phi_data,yerr=asymmetric_err,color='k',fmt='s',
        ecolor='k',markersize=5,capsize=5,capthick=0.5,
        label='data',zorder=10)
    for idx in range(len(result[0][0])):
        plt.plot(result[0][0][idx],result[0][1][idx],color='lightgray',
            linestyle='-',alpha=0.5,zorder=0,label='model')
    for idx in range(len(result[1][0])):
        plt.plot(result[1][0][idx],result[1][1][idx],color='lightgray',
            linestyle='-',alpha=0.5,zorder=1)
    for idx in range(len(result[2][0])):
        plt.plot(result[2][0][idx],result[2][1][idx],color='lightgray',
            linestyle='-',alpha=0.5,zorder=2)
    for idx in range(len(result[3][0])):
        plt.plot(result[3][0][idx],result[3][1][idx],color='lightgray',
            linestyle='-',alpha=0.5,zorder=3)
    for idx in range(len(result[4][0])):
        plt.plot(result[4][0][idx],result[4][1][idx],color='lightgray',
            linestyle='-',alpha=0.5,zorder=4)
    lower_err = np.log10((10**phi_model_bf) - err_tot_model_bf)
    upper_err = np.log10((10**phi_model_bf) + err_tot_model_bf)
    lower_err = phi_model_bf - lower_err
    upper_err = upper_err - phi_model_bf
    asymmetric_err = [lower_err, upper_err]
    # REMOVED BEST FIT ERROR
    plt.errorbar(max_model_bf,phi_model_bf,
        color='mediumorchid',fmt='-s',ecolor='mediumorchid',markersize=3,
        capsize=5,capthick=0.5,label='best fit',zorder=10)
    plt.ylim(-4,-1)
    if mf_type == 'smf':
        plt.xlabel(r'\boldmath$\log_{10}\ M_\star \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$', fontsize=20)
    elif mf_type == 'bmf':
        plt.xlabel(r'\boldmath$\log_{10}\ M_{b} \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$', fontsize=20)
    plt.ylabel(r'\boldmath$\Phi \left[\mathrm{dex}^{-1}\,\mathrm{Mpc}^{-3}\,\mathrm{h}^{3} \right]$', fontsize=20)
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = OrderedDict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys(), loc='best',prop={'size': 20})
    plt.annotate(r'$\boldsymbol\chi ^2 \approx$ {0}'.format(np.round(bf_chi2,2)), 
        xy=(0.1, 0.1), xycoords='axes fraction', bbox=dict(boxstyle="square", 
        ec='k', fc='lightgray', alpha=0.5), size=15)
    if mf_type == 'smf':
        plt.savefig(path_to_figures + 'smf_emcee_{0}.png'.format(survey))
    elif mf_type == 'bmf':
        plt.savefig(path_to_figures + 'bmf_emcee_{0}.png'.format(survey))

def plot_xmhm(result, gals_bf, halos_bf, gals_data, halos_data, gals_b10, \
    halos_b10, bf_chi2):
    """
    Plot SMHM from data, best fit param values, param values corresponding to 
    68th percentile 1000 lowest chi^2 values and behroozi 2010 param values

    Parameters
    ----------
    result: multidimensional array
        Array of central galaxy and halo masses
    
    gals_bf: array
        Array of y-axis stellar mass values for best fit SMHM

    halos_bf: array
        Array of x-axis halo mass values for best fit SMHM
    
    gals_data: array
        Array of y-axis stellar mass values for data SMF

    halos_data: array
        Array of x-axis halo mass values for data SMF

    gals_b10: array
        Array of y-axis stellar mass values for behroozi 2010 SMHM

    halos_b10: array
        Array of x-axis halo mass values for behroozi 2010 SMHM

    Returns
    ---------
    Nothing; SMHM plot is saved in figures repository
    """
    if survey == 'resolvea':
        line_label = 'RESOLVE-A'
    elif survey == 'resolveb':
        line_label = 'RESOLVE-B'
    elif survey == 'eco':
        line_label = 'ECO'
    
    x_bf,y_bf,y_std_bf,y_std_err_bf = Stats_one_arr(halos_bf,\
    gals_bf,base=0.4,bin_statval='center')
    x_b10,y_b10,y_std_b10,y_std_err_b10 = Stats_one_arr(halos_b10,\
        gals_b10,base=0.4,bin_statval='center')
    x_data,y_data,y_std_data,y_std_err_data = Stats_one_arr(halos_data,\
        gals_data,base=0.4,bin_statval='center')
    # y_std_err_data = err_data

    fig1 = plt.figure(figsize=(10,10))
    # NOT PLOTTING DATA RELATION
    # plt.errorbar(x_data,y_data,yerr=y_std_err_data,color='k',fmt='-s',\
    #     ecolor='k',markersize=4,capsize=5,capthick=0.5,\
    #         label='{0}'.format(line_label),zorder=10)

    plt.errorbar(x_b10,y_b10, color='k',fmt='--s',\
        markersize=3, label='Behroozi10', zorder=10, alpha=0.7)

    for idx in range(len(result[0][0])):
        x_model,y_model,y_std_model,y_std_err_model = \
            Stats_one_arr(result[0][4][idx],result[0][3][idx],base=0.4,\
                bin_statval='center')
        plt.plot(x_model,y_model,color='lightgray',linestyle='-',alpha=0.5,\
            zorder=0,label='model')
    for idx in range(len(result[1][0])):
        x_model,y_model,y_std_model,y_std_err_model = \
            Stats_one_arr(result[1][4][idx],result[1][3][idx],base=0.4,\
                bin_statval='center')
        plt.plot(x_model,y_model,color='lightgray',linestyle='-',alpha=0.5,\
            zorder=1)
    for idx in range(len(result[2][0])):
        x_model,y_model,y_std_model,y_std_err_model = \
            Stats_one_arr(result[2][4][idx],result[2][3][idx],base=0.4,\
                bin_statval='center')
        plt.plot(x_model,y_model,color='lightgray',linestyle='-',alpha=0.5,\
            zorder=2)
    for idx in range(len(result[3][0])):
        x_model,y_model,y_std_model,y_std_err_model = \
            Stats_one_arr(result[3][4][idx],result[3][3][idx],base=0.4,\
                bin_statval='center')
        plt.plot(x_model,y_model,color='lightgray',linestyle='-',alpha=0.5,\
            zorder=3)
    for idx in range(len(result[4][0])):
        x_model,y_model,y_std_model,y_std_err_model = \
            Stats_one_arr(result[4][4][idx],result[4][3][idx],base=0.4,\
                bin_statval='center')
        plt.plot(x_model,y_model,color='lightgray',linestyle='-',alpha=0.5,\
            zorder=4)

    # REMOVED ERROR BAR ON BEST FIT
    plt.errorbar(x_bf,y_bf,color='mediumorchid',fmt='-s',ecolor='mediumorchid',\
        markersize=4,capsize=5,capthick=0.5,label='best fit',zorder=10)

    if survey == 'resolvea' and mf_type == 'smf':
        plt.xlim(10,14)
    else:
        plt.xlim(10,)
    plt.xlabel(r'\boldmath$\log_{10}\ M_{h} \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$',fontsize=20)
    if mf_type == 'smf':
        if survey == 'eco':
            plt.ylim(np.log10((10**8.9)/2.041),)
        elif survey == 'resolvea':
            plt.ylim(np.log10((10**8.9)/2.041),13)
        elif survey == 'resolveb':
            plt.ylim(np.log10((10**8.7)/2.041),)
        plt.ylabel(r'\boldmath$\log_{10}\ M_\star \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$',fontsize=20)
    elif mf_type == 'bmf':
        if survey == 'eco' or survey == 'resolvea':
            plt.ylim(np.log10((10**9.4)/2.041),)
        elif survey == 'resolveb':
            plt.ylim(np.log10((10**9.1)/2.041),)
        plt.ylabel(r'\boldmath$\log_{10}\ M_{b} \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$',fontsize=20)
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = OrderedDict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys(), loc='best',prop={'size': 20})
    plt.annotate(r'$\boldsymbol\chi ^2 \approx$ {0}'.format(np.round(bf_chi2,2)), 
        xy=(0.8, 0.1), xycoords='axes fraction', bbox=dict(boxstyle="square", 
        ec='k', fc='lightgray', alpha=0.5), size=15)
    if mf_type == 'smf':
        plt.savefig(path_to_figures + 'smhm_emcee_{0}.png'.format(survey))
    elif mf_type == 'bmf':
        plt.savefig(path_to_figures + 'bmhm_emcee_{0}.png'.format(survey))

def plot_xmhm_data_mocks(gals_data, halos_data, xmhm_mocks, 
    gals_bf, halos_bf):
    """ This function plots mass relations from survey mocks and data"""
    x_bf,y_bf,y_std_bf,y_std_err_bf = Stats_one_arr(halos_bf,
    gals_bf,base=0.4,bin_statval='center')
    x_data,y_data,y_std_data,y_std_err_data = Stats_one_arr(halos_data,
        gals_data, base=0.4, bin_statval='center')
    # y_std_err_data = err_data

    fig1 = plt.figure(figsize=(10,10))
    x_mocks, y_mocks, y_std_err_mocks = xmhm_mocks[0], xmhm_mocks[1], \
        xmhm_mocks[2]
    y_std_err_data = np.std(y_mocks, axis=0)
    # for i in range(len(x_mocks)):
    #     plt.errorbar(x_mocks[i],y_mocks[i],yerr=y_std_err_mocks[i],
    #         color='lightgray',fmt='-s', ecolor='lightgray', markersize=4, 
    #         capsize=5, capthick=0.5, label=r'mocks',zorder=5)
    plt.errorbar(x_data,y_data,yerr=y_std_err_data,color='k',fmt='s',
        ecolor='k',markersize=5,capsize=5,capthick=0.5,\
            label=r'data',zorder=10)
    plt.errorbar(x_bf,y_bf,color='mediumorchid',fmt='-s',
        ecolor='mediumorchid',markersize=5,capsize=5,capthick=0.5,\
            label=r'best-fit',zorder=20)


    plt.xlabel(r'\boldmath$\log_{10}\ M_{h} \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$',fontsize=20)
    if mf_type == 'smf':
        if survey == 'eco' or survey == 'resolvea':
            plt.ylim(np.log10((10**8.9)/2.041),)
        elif survey == 'resolveb':
            plt.ylim(np.log10((10**8.7)/2.041),)
        plt.ylabel(r'\boldmath$\log_{10}\ M_\star \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$',fontsize=20)
    elif mf_type == 'bmf':
        if survey == 'eco' or survey == 'resolvea':
            plt.ylim(np.log10((10**9.4)/2.041),)
        elif survey == 'resolveb':
            plt.ylim(np.log10((10**9.1)/2.041),)
        plt.ylabel(r'\boldmath$\log_{10}\ M_{b} \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$',fontsize=20)
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = OrderedDict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys(), loc='best',prop={'size': 15})
    # plt.savefig(path_to_figures + 'mocks_data_xmhm_{0}.png'.format(survey))
    plt.show()

def behroozi10(logmstar, bf_params):
    """ 
    This function calculates the B10 stellar to halo mass relation 
    using the functional form 
    """
    M_1, Mstar_0, beta, delta = bf_params[:4]
    gamma = model_init.param_dict['smhm_gamma_0']
    second_term = (beta*np.log10((10**logmstar)/(10**Mstar_0)))
    third_term_num = (((10**logmstar)/(10**Mstar_0))**delta)
    third_term_denom = (1 + (((10**logmstar)/(10**Mstar_0))**(-gamma)))
    logmh = M_1 + second_term + (third_term_num/third_term_denom) - 0.5

    return logmh

def debug_xmhm():

    bf_params_bmf = np.array([12.23321941, 10.53554995, 0.5430062, 0.57290598, 0.36211791])
    bf_params_smf = np.array([12.32381675, 10.56581819, 0.4276319, 0.7457711 , 0.34784431])
    behroozi10_params = np.array([12.35, 10.72, 0.44, 0.57, 0.15])

    mstar_min = np.round(np.log10((10**6.5)/2.041),1) 
    mstar_max = np.round(np.log10((10**11.8)/2.041),1) 
    logmstar_arr = np.linspace(mstar_min, mstar_max, 500) 

    logmh_bary = behroozi10(logmstar_arr, bf_params_bmf)
    logmh_stellar = behroozi10(logmstar_arr, bf_params_smf)
    logmh_b10 = behroozi10(logmstar_arr, behroozi10_params)


    x_bary,y_bary,y_std_bary,y_std_err_bary = Stats_one_arr(logmh_bary,\
    logmstar_arr,base=0.4,bin_statval='center')
    x_star,y_star,y_std_star,y_std_err_star = Stats_one_arr(logmh_stellar,\
    logmstar_arr,base=0.4,bin_statval='center')
    x_b10,y_b10,y_std_b10,y_std_err_b10 = Stats_one_arr(logmh_b10,\
    logmstar_arr,base=0.4,bin_statval='center')

    fig3 = plt.figure(figsize=(10,10))
    # plt.plot(logmh_bary, logmstar_arr, c='r')
    # plt.plot(logmh_stellar, logmstar_arr, c='b')
    # plt.plot(logmh_b10, logmstar_arr, c='k')
    plt.errorbar(x_bary,y_bary,yerr=y_std_err_bary,color='r',fmt='-s',ecolor='r',\
        markersize=4,capsize=5,capthick=0.5,label=r'baryonic',zorder=10)
    plt.errorbar(x_star,y_star,yerr=y_std_err_star,color='b',fmt='-s',ecolor='b',\
        markersize=4,capsize=5,capthick=0.5,label=r'stellar',zorder=20)
    plt.errorbar(x_b10,y_b10,yerr=y_std_err_b10,color='k',fmt='-s',ecolor='k',\
            markersize=4,capsize=5,capthick=0.5,label=r'Behroozi10',zorder=30)
    plt.xlabel(r'\boldmath$\log_{10}\ M_{h} \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$',fontsize=15)
    plt.ylabel(r'\boldmath$\log_{10}\ M_\star \left[\mathrm{M_\odot}\, \mathrm{h}^{-1} \right]$',fontsize=15)
    plt.legend(loc='best',prop={'size': 10})
    plt.show()

def args_parser():
    """
    Parsing arguments passed to populate_mock.py script

    Returns
    -------
    args: 
        Input arguments to the script
    """
    print('Parsing in progress')
    parser = argparse.ArgumentParser()
    parser.add_argument('machine', type=str, \
        help='Options: mac/bender')
    parser.add_argument('survey', type=str, \
        help='Options: eco/resolvea/resolveb')
    parser.add_argument('mf_type', type=str, \
        help='Options: smf/bmf')
    parser.add_argument('nproc', type=int, help='Number of processes',\
        default=1)
    args = parser.parse_args()
    return args

def main(args):
    """
    Main function that calls all other functions
    
    Parameters
    ----------
    args: 
        Input arguments to the script

    """
    global model_init
    global survey
    global path_to_figures
    global mf_type

    survey = args.survey
    machine = args.machine
    nproc = args.nproc
    mf_type = args.mf_type

    dict_of_paths = cwpaths.cookiecutter_paths()
    path_to_raw = dict_of_paths['raw_dir']
    path_to_proc = dict_of_paths['proc_dir']
    path_to_interim = dict_of_paths['int_dir']
    path_to_figures = dict_of_paths['plot_dir']
    path_to_external = dict_of_paths['ext_dir']

    if machine == 'bender':
        halo_catalog = '/home/asadm2/.astropy/cache/halotools/halo_catalogs/'\
                    'vishnu/rockstar/vishnu_rockstar_test.hdf5'
    elif machine == 'mac':
        halo_catalog = path_to_raw + 'vishnu_rockstar_test.hdf5'

    if mf_type == 'smf':
        path_to_proc = path_to_proc + 'smhm_run4_errjk/'
    elif mf_type == 'bmf':
        path_to_proc = path_to_proc + 'bmhm_run2/'

    chi2_file = path_to_proc + '{0}_chi2.txt'.format(survey)

    if mf_type == 'smf' and survey == 'eco':
        chain_file = path_to_proc + 'mcmc_{0}.dat'.format(survey)
    else:
        chain_file = path_to_proc + 'mcmc_{0}_raw.txt'.format(survey)

    if survey == 'eco':
        catl_file = path_to_raw + "eco_all.csv"
        path_to_mocks = path_to_external + 'ECO_mvir_catls/'
    elif survey == 'resolvea' or survey == 'resolveb':
        catl_file = path_to_raw + "RESOLVE_liveJune2019.csv"
        if survey == 'resolvea':
            path_to_mocks = path_to_external + 'RESOLVE_A_mvir_catls/'
        else:
            path_to_mocks = path_to_external + 'RESOLVE_B_mvir_catls/'

    print('Reading chi-squared file')
    chi2 = read_chi2(chi2_file)
    print('Reading mcmc chain file')
    mcmc_table = read_mcmc(chain_file)
    print('Reading catalog')
    catl, volume, cvar, z_median = read_data_catl(catl_file, survey)
    print('Getting data in specific percentile')
    mcmc_table_pctl, bf_params, bf_chi2 = \
        get_paramvals_percentile(mcmc_table, 68, chi2)

    # print('Retrieving stellar mass from catalog')
    # stellar_mass_arr = catl.logmstar.values
    # if mf_type == 'smf':
    #     maxis_data, phi_data, err_data_, bins_data, counts_data = \
    #         diff_smf(stellar_mass_arr, volume, False)
    # elif mf_type == 'bmf':
    #     gas_mass_arr = catl.logmgas.values
    #     bary_mass_arr = calc_bary(stellar_mass_arr, gas_mass_arr)
    #     maxis_data, phi_data, err_data_, bins_data, counts_data = \
    #         diff_bmf(bary_mass_arr, volume, False)
    # print('Jackknife survey')
    # err_data_mf, err_data_xmhm = jackknife(catl, volume)
    print('Initial population of halo catalog')
    model_init = halocat_init(halo_catalog, z_median)

    # print('Retrieving Behroozi 2010 centrals')
    # model_init.mock.populate()
    # if survey == 'eco' or survey == 'resolvea':
    #     if mf_type == 'smf':
    #         limit = np.round(np.log10((10**8.9) / 2.041), 1)
    #     elif mf_type == 'bmf':
    #         limit = np.round(np.log10((10**9.4) / 2.041), 1)
    # elif survey == 'resolveb':
    #     if mf_type == 'smf':
    #         limit = np.round(np.log10((10**8.7) / 2.041), 1)
    #     elif mf_type == 'bmf':
    #         limit = np.round(np.log10((10**9.1) / 2.041), 1)
    # sample_mask = model_init.mock.galaxy_table['stellar_mass'] >= 10**limit
    # gals_b10 = model_init.mock.galaxy_table[sample_mask]
    # cen_gals_b10, cen_halos_b10 = get_centrals_mock(gals_b10)

    print('Retrieving survey centrals')
    cen_gals_data, cen_halos_data = get_centrals_data(catl)

    # Need following two lines ONLY if using groupmass_s for RESOLVE-A
    cen_halos_data = np.array(list(cen_halos_data.values[:65]) + list(cen_halos_data.values[66:]))
    cen_gals_data = np.array(list(cen_gals_data.values[:65]) + list(cen_gals_data.values[66:]))

    # print('Multiprocessing')
    # result = mp_init(mcmc_table_pctl, nproc)
    print('Getting best fit model and centrals')
    maxis_bf, phi_bf, err_tot_bf, counts_bf, cen_gals_bf, cen_halos_bf = \
        get_best_fit_model(bf_params)

    # print('Plotting MF')
    # plot_mf(result, maxis_bf, phi_bf, err_tot_bf, maxis_data, phi_data, 
    #     err_data_mf, bf_chi2)

    # print('Plotting XMHM')
    # plot_xmhm(result, cen_gals_bf, cen_halos_bf, cen_gals_data, cen_halos_data,
    #     cen_gals_b10, cen_halos_b10, bf_chi2)   

    xmhm_mocks = get_xmhm_mocks(survey, path_to_mocks, mf_type)

    plot_xmhm_data_mocks(cen_gals_data, cen_halos_data, 
        xmhm_mocks, cen_gals_bf, cen_halos_bf)

# Main function
if __name__ == '__main__':
    args = args_parser()
    main(args) 


