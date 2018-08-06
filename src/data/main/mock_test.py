#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug  3 14:10:35 2018

@author: asadm2
"""

from cosmo_utils.utils import work_paths as cwpaths
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from scipy import interpolate
from matplotlib import rc
import pandas as pd
import numpy as np
import math

### Paths
dict_of_paths = cwpaths.cookiecutter_paths()
path_to_raw = dict_of_paths['raw_dir']
path_to_interim = dict_of_paths['int_dir']
path_to_figures = dict_of_paths['plot_dir']

###Formatting for plots and animation
rc('font',**{'family':'sans-serif','sans-serif':['Helvetica']},size=15)
rc('text', usetex=True)

eco_obs_catalog = pd.read_csv(path_to_raw + 'gal_Lr_Mb_Re.txt',\
                              delimiter='\s+',header=None,skiprows=2,\
                              names=['M_r','logmbary','Re'])

def fit_func(M,phi_star,M_star,alpha):
    const = 0.4*np.log(10)*phi_star
    first_exp_term = 10**(0.4*(alpha+1)*(M-M_star))
    second_exp_term = np.exp(-10**(0.4*(M-M_star)))
    return const*first_exp_term*second_exp_term

def cum_num_dens(data,nbins,volume,mag_bool):
    #Unnormalized histogram and bin edges
    freq,edg = np.histogram(data,bins=nbins)     
    bin_centers = 0.5*(edg[1:]+edg[:-1])
    err_poiss = np.sqrt(freq)/volume
    freq = freq/volume 
    if mag_bool:
        n = np.cumsum(freq) 
    else:
        n = np.cumsum(np.flip(freq,0))
        n = np.flip(n,0)
    return bin_centers,n,err_poiss

def num_bins(data_arr):
    q75, q25 = np.percentile(data_arr, [75 ,25])
    iqr = q75 - q25
    num_points = len(data_arr)
    h =2*iqr*(num_points**(-1/3))
    n_bins = math.ceil((max(data_arr)-min(data_arr))/h) #Round up number   
    return n_bins

v_eco = 442650.9037900876 #ECO without buffer

##METHOD 1 using VC's method on unique M_r values
Mr_unique = np.unique(eco_obs_catalog.M_r.values)
Mr_all = eco_obs_catalog.M_r.values
n_Mr = np.array([np.where(Mr_all < xx)[0].size + 1 for xx in Mr_unique])
n_Mr = n_Mr/v_eco

##METHOD 2 my method but using unique M_r values for bins
nbins = Mr_unique
bin_centers,n_Mr_2,err_poiss = cum_num_dens(Mr_all,nbins,v_eco,mag_bool=True)

##METHOD 3 my method with my method of binning using num_bins function
nbins = num_bins(Mr_all)
bin_centers_2,n_Mr_3,err_poiss = cum_num_dens(Mr_all,nbins,v_eco,mag_bool=True)

### Using SF to fit all data until -17
min_Mr = min(Mr_all)
max_Mr = max(Mr_all)
p0 = [10**-2,-22,-1.1] #initial guess for phi_star,M_star,alpha
params_alldata = curve_fit(fit_func, bin_centers_2,n_Mr_3,p0,\
                           maxfev=20000)
fit_alldata = fit_func(np.linspace(min_Mr,max_Mr),\
                       params_alldata[0][0],params_alldata[0][1],\
                       params_alldata[0][2])

### Using SF to fit data until -17.33 and extrapolating SF using the same 
### parameters until -17
M_r_cut = [value for value in Mr_all if value <= -17.33]
max_M_r_cut = max(M_r_cut)
nbins = num_bins(M_r_cut)
bin_centers_cut,n_Mr_cut,err_poiss_cut = cum_num_dens(M_r_cut,nbins,v_eco,\
                                                      mag_bool=True)
params_noextrap = curve_fit(fit_func,bin_centers_cut,n_Mr_cut,p0,\
                            maxfev=20000)
fit_noextrap = fit_func(np.linspace(min_Mr,max_M_r_cut),\
                        params_noextrap[0][0],params_noextrap[0][1],\
                        params_noextrap[0][2])

fit_extrap = fit_func(np.linspace(max_Mr,max_M_r_cut),\
                      params_noextrap[0][0],params_noextrap[0][1],\
                      params_noextrap[0][2])

fig1 = plt.figure(figsize=(10,8))
plt.yscale('log')
plt.axvline(-17.33,ls='--',c='k',label='ECO/RESOLVE-A')
plt.axvline(-17,ls='--',c='r',label='RESOLVE-B')
plt.gca().invert_xaxis()
#plt.scatter(Mr_unique,n_Mr,c='r',s=5,label='unique bins')
plt.scatter(bin_centers,n_Mr_2,c='g',s=5,label='cum sum with unique bins')
#plt.scatter(bin_centers_2,n_Mr_3,c='b',s=5,label='cum sum with FD bins')
plt.plot(np.linspace(min_Mr,max_Mr),fit_alldata,'--g',label='all data fit')
plt.plot(np.linspace(max_Mr,max_M_r_cut),fit_extrap,'--y',label='extrap')
plt.plot(np.linspace(min_Mr,max_M_r_cut),fit_noextrap,'--k',\
         label='data fit until -17.33')
plt.xlabel(r'$M_{r}$')
plt.ylabel(r'$n(< M_{r})/\mathrm{Mpc}^{-3}$')
plt.legend(loc='best')
plt.show()

### Halo data
halo_prop_table = pd.read_csv(path_to_interim + 'halo_vpeak.csv',header=None,\
                              names=['vpeak'])
v_sim = 130**3
vpeak = halo_prop_table.vpeak.values
nbins = num_bins(vpeak)
bin_centers_vpeak,n_vpeak,err_poiss = cum_num_dens(vpeak,nbins,v_sim,\
                                                   mag_bool=False)
f_h = interpolate.interp1d(bin_centers_vpeak,n_vpeak,fill_value="extrapolate",\
                           kind=3)
x_h = np.linspace(min(vpeak),max(vpeak),num=200)
ynew_h = f_h(x_h)

fig2 = plt.figure()
plt.xscale('log')
plt.yscale('log')
plt.xlabel(r'$v_{peak} /\mathrm{km\ s^{-1}}$')
plt.ylabel(r'$n(> v_{peak})/\mathrm{Mpc}^{-3}$')
plt.scatter(bin_centers_vpeak,n_vpeak,label='data',s=2)
plt.plot(x_h,ynew_h,'--k',label='interp/exterp')
plt.legend(loc='best')
plt.show()

f_h = interpolate.interp1d(n_vpeak,bin_centers_vpeak,fill_value="extrapolate")
#f_Mr = interpolate.interp1d(bin_centers_cut, n_Mr_cut,fill_value="extrapolate",\
#                           kind=3)
halo_vpeak_sham = []
n_Mr_arr = []
for mag_value in Mr_all:
    n_Mr = fit_func(mag_value,params_noextrap[0][0],params_noextrap[0][1],\
                    params_noextrap[0][2])
    n_Mr_arr.append(n_Mr)
for value in n_Mr_arr:
    halo_vpeak = f_h(value)
    halo_vpeak_sham.append(halo_vpeak)
    
fig3 = plt.figure()
#plt.xscale('log')
plt.gca().invert_yaxis()
plt.scatter(halo_vpeak_sham,Mr_all,s=5)
plt.ylabel(r'$M_{r}$')
plt.xlabel(r'$v_{peak} /\mathrm{km\ s^{-1}}$')
plt.show()
