import numpy as np
import lmfit as lm
from scipy import signal
from scipy.stats import gamma,expon
from lmfit.models import ExponentialModel
import pandas as pd
import os.path
import sys

k,ga,D = 1.0,1.0,1.0
delta_t=0.01
ampl = np.sqrt(2*D*delta_t)
N=100

# repeat 100 times
for count in range(100):
    if os.path.isfile("repeat.csv"):
        repeat = pd.read_csv("repeat.csv")
    else:
        repeat_dict={"mu_A" : np.array([1.0]),
                     "sd_A" : np.array([10.0]),
                     "mu_D" : np.array([1.0]),
                     "sd_D" : np.array([10.0])}
        repeat = pd.DataFrame(repeat_dict)

    print(repeat)
    # take the last entry as the prior for this run
    last_entry=len(repeat)

    mu_A=repeat["mu_A"][last_entry-1]
    sd_A=repeat["sd_A"][last_entry-1]
    mu_D=repeat["mu_D"][last_entry-1]
    sd_D=repeat["sd_D"][last_entry-1]

    datadict={}

    # random force
    w=np.random.normal(0,1,N)

    # differential equation x_i = x_(i-1) - k/gamma*x_(i-1) + sqrt(2*D*delta_t)*w_i
    from itertools import accumulate
    def next_point(x,y):
        return x - k/ga*x*delta_t + ampl*y

    x = np.fromiter(accumulate(w, next_point),np.float)

    datadict['x']=x

    print("std: ",x.std(),"mean: ",x.mean())

    # see http://docs.scipy.org/doc/scipy-0.15.1/reference/generated/scipy.signal.fftconvolve.html
    autocorr = signal.fftconvolve(x, x[::-1], mode='full')
    n=len(autocorr)
    autocorr=autocorr[int((n-1)/2):]*2.0/(n+1)
    datadict['acf']=autocorr

    df=pd.DataFrame(datadict)
    df.to_csv('data.csv')

    mod = ExponentialModel()
    y = autocorr[:100]
    t = np.arange(100)

    acf_dict={'acf':y}
    acf_df=pd.DataFrame(acf_dict)
    acf_df.to_csv('acf'+str(last_entry)+'.csv')

    pars = mod.guess(y, x=t)
    out  = mod.fit(y, pars, x=t)
    print(out.fit_report(min_correl=0.25))

    ampl=out.best_values['amplitude']
    decay=out.best_values['decay']

    fits_dict={'Ampl' : np.array([ampl]),
               'decay' : np.array([decay])}
    fits=pd.DataFrame(fits_dict)

    if os.path.isfile("fits.csv"):
        old_fits=pd.read_csv("fits.csv")
        print(old_fits)
        fits = pd.concat([old_fits,fits],ignore_index=True)

    fits.to_csv("fits.csv",index=False)

    # now lets model this data using pymc
    import pymc3 as pm
    # define the model/function for diffusion in a harmonic potential
    DHP_model = pm.Model()
    with DHP_model:
        D = pm.Gamma('D',mu=mu_D,sd=sd_D)
        A = pm.Gamma('A',mu=mu_A,sd=sd_A)
    
        S=1.0-pm.exp(-2.0*delta_t*D/A)
    
        ss=pm.exp(-delta_t*D/A)
        
        path=pm.Normal('path_0',mu=0.0, tau=1/A, observed=x[0])
        for i in range(1,N):
            path = pm.Normal('path_%i' % i,
                                mu=path*ss,
                                tau=1.0/A/S,
                                observed=x[i])

    with DHP_model:
        start = pm.find_MAP()
        print(start)
        trace = pm.sample(100000, start=start)

    mean_D=trace['D'].mean()
    std_D=trace['D'].std()
    print('mean_D: ',mean_D,'std_D: ',std_D)
    scale_D=std_D**2/mean_D
    alpha_D=mean_D/scale_D
    print('alpha_D: ',alpha_D,'scale_D: ',scale_D)

    mean_A=trace['A'].mean()
    std_A=trace['A'].std()
    print('mean_A: ',mean_A,'std_A: ',std_A)
    scale_A=std_A**2/mean_A
    alpha_A=mean_A/scale_A
    print('alpha_A: ',alpha_A,'scale_A: ',scale_A)

    repeat_dict2={"mu_A" : np.array([mean_A]),
                "sd_A" : np.array([std_A]),
                "mu_D" : np.array([mean_D]),
                "sd_D" : np.array([std_D])}

    # add new gamma distributions to file
    repeat2 = pd.DataFrame(repeat_dict2)
    repeat_new=pd.concat([repeat,repeat2],ignore_index=True)
    repeat_new.to_csv("repeat.csv", index=False)

    # save the data
    tracedict={}
    tracedict['D']=trace['D']
    tracedict['D_log']=trace['D_log']
    tracedict['A']=trace['A']
    tracedict['A_log']=trace['A_log']

    tdf=pd.DataFrame(tracedict)
    tdf.to_csv('trace'+str(last_entry)+'.csv',index=False)
