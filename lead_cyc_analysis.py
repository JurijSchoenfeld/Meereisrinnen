import numpy as np
import case_information as ci
import leads
import matplotlib.pyplot as plt
import data_science as ds
import cartopy.crs as ccrs
from datetime import date, timedelta
from scipy.stats import ttest_ind
import pickle
import ice_divergence as ice_div


class Analysis:
    def __init__(self, date1, date2, extent=ci.arctic_extent, collect_ice_div=True):
        self.nrows = 2
        self.ncols = 4
        self.extent = extent
        self.dates = ds.time_delta(date1, date2)
        self.leads, self.cycs, self.cycs_past, self.divs = [], [], [], []
        self.lon, self.lat = leads.CoordinateGridAllY().lon, leads.CoordinateGridAllY().lat
        self.delta_days = 3
        self.sic_filter = 95.

        self.collect_ice_div = collect_ice_div
        self.missing_dates = []

    def collect_leads_cycs(self, return_for_export=False):
        # print(self.dates)
        for date in self.dates:
            print(date)
            # load class
            leadally = leads.LeadAllY(date)
            # get lead data
            lead_data = leadally.lead_data
            lead_data[100 * leadally.sic_data <= self.sic_filter] = np.nan
            self.leads.append(lead_data)

            # get cyclone data from current and last day
            # cyc = .01 * leads.Era5Regrid('cyclone_occurence').get_variable(date).data
            cyc = 1.0 * leadally.cyc_data

            # cluster cells as cyclone if cyclone frequency >= .5
            cyc[cyc <= .25] = np.nan
            cyc[cyc > .25] = 1.

            cyc_past = np.copy(cyc)
            for i in range(1, self.delta_days + 1):
                past_day = ds.datetime_to_string(ds.string_time_to_datetime(date) - timedelta(days=i))
                cyc_p = 1. * leads.LeadAllY(past_day).cyc_data
                cyc_p[cyc_p <= .25] = np.nan
                cyc_p[cyc_p > .25] = 1.
                cyc_p[cyc_past == 1.] = 1.
                cyc_past = np.copy(cyc_p)

            self.cycs.append(cyc)
            self.cycs_past.append(cyc_past)

            if self.collect_ice_div:
                # load ice divergence data and coords
                try:
                    self.divs.append(leadally.ice_div.T)
                except FileNotFoundError:
                    print('Could not find date: ', date)
                    print('Add empty array to list, should not affect results')
                    self.divs.append(np.empty(self.divs[-1].shape))
                    self.missing_dates.append(date)

        if self.missing_dates:
            print('missing dates: ', self.missing_dates)

        if return_for_export:
            return self.leads, self.cycs

    def cluster_leads(self, matrix3d=False):
        # get average lead fraction for all time instances with cyclone (today and/or yesterday), without cyclone
        self.collect_leads_cycs()
        print('finished collecting\nstart clustering')
        no_cyc_leads, cyc_leads, no_cyc_prior_leads, cyc_prior_leads = [], [], [], []
        no_cyc_divs, cyc_divs = [], []

        for lead, cyc, cyc_past, div in zip(self.leads, self.cycs, self.cycs_past, self.divs):
            no_cyc_lead, cyc_lead, cyc_prior_lead, no_cyc_prior_lead = np.copy(lead), np.copy(lead), np.copy(
                lead), np.copy(lead)

            no_cyc_lead[~np.isnan(cyc)] = np.nan
            cyc_lead[np.isnan(cyc)] = np.nan
            cyc_prior_lead[np.isnan(cyc_past)] = np.nan
            no_cyc_prior_lead[~np.isnan(cyc_past)] = np.nan

            no_cyc_leads.append(no_cyc_lead)
            cyc_leads.append(cyc_lead)
            cyc_prior_leads.append(cyc_prior_lead)
            no_cyc_prior_leads.append(no_cyc_prior_lead)

            if self.collect_ice_div:
                no_cyc_div, cyc_div = np.copy(div), np.copy(div)
                no_cyc_div[~np.isnan(cyc_past)] = np.nan
                cyc_div[np.isnan(cyc_past)] = np.nan
                no_cyc_divs.append(no_cyc_div)
                cyc_divs.append(cyc_div)

        if matrix3d and self.collect_ice_div:
            return np.array(no_cyc_leads), np.array(cyc_leads), np.array(cyc_prior_leads), np.array(no_cyc_prior_leads), \
                   np.array(no_cyc_divs), np.array(cyc_divs)

        elif matrix3d:
            return np.array(no_cyc_leads), np.array(cyc_leads), np.array(cyc_prior_leads), np.array(no_cyc_prior_leads)

        elif self.collect_ice_div:
            return np.nanmean(np.array(no_cyc_leads), axis=0), np.nanmean(np.array(cyc_leads), axis=0), \
                   np.nanmean(np.array(cyc_prior_leads), axis=0), np.nanmean(np.array(no_cyc_prior_leads), axis=0), \
                   np.nanmean(np.array(no_cyc_divs), axis=0), np.nanmean(np.array(cyc_divs), axis=0)

        else:
            return np.nanmean(np.array(no_cyc_leads), axis=0), np.nanmean(np.array(cyc_leads), axis=0), \
                   np.nanmean(np.array(cyc_prior_leads), axis=0), np.nanmean(np.array(no_cyc_prior_leads), axis=0)

    def export_clustered_leads(self, m3d):
        with open(f'./pickles/clustered_leads_m3d={m3d}_{self.collect_ice_div}_{self.sic_filter}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}.pkl', 'wb') as filehandler:
            if m3d:
                pickle.dump(self.cluster_leads(matrix3d=True),  filehandler)
            else:
                pickle.dump(self.cluster_leads(matrix3d=False),  filehandler)

    def export_collection(self):
        with open(f'./pickles/collections_{self.sic_filter}_{self.dates[0]}_{self.dates[-1]}.pkl', 'wb') as filehandler:
            pickle.dump(self.collect_leads_cycs(return_for_export=True),  filehandler)

    def setup_plot(self):
        fig, ax = plt.subplots(self.nrows, self.ncols,
                               subplot_kw={"projection": ccrs.NearsidePerspective(-45, 90)})
        fig.set_size_inches(20, 20)
        try:
            for i, a in enumerate(ax.flatten()):
                a.coastlines(resolution='50m')
                a.set_extent(self.extent, crs=ccrs.PlateCarree())
            return fig, ax
        except AttributeError:
            print('create fig with only one ax')
            ax.coastlines(resolution='50m')
            ax.set_extent(self.extent, crs=ccrs.PlateCarree())
            return fig, ax

    def plot(self):
        self.nrows = 3
        self.ncols = 6
        nim = self.nrows * self.ncols
        self.collect_leads_cycs()
        for i in range(int(np.floor(len(self.dates) / nim))):
            fig, ax = self.setup_plot()
            for lead, cyc, date, pcyc, a in zip(self.leads[i * nim:(i + 1) * nim], self.cycs[i * nim:(i + 1) * nim],
                                                self.dates[i * nim:(i + 1) * nim],
                                                self.cycs_past[i * nim:(i + 1) * nim], ax.flatten()):
                print(date)
                lead[lead <= .25] = np.nan
                a.pcolormesh(self.lon, self.lat, pcyc, cmap='winter', vmin=0, vmax=.1, transform=ccrs.PlateCarree())
                a.pcolormesh(self.lon, self.lat, cyc, cmap='summer', vmin=0, vmax=.1, transform=ccrs.PlateCarree())
                a.pcolormesh(self.lon, self.lat, lead, cmap='Reds', vmin=0, vmax=1, transform=ccrs.PlateCarree())
                a.set_title(date, fontsize=20)

            plt.tight_layout()
            plt.savefig(f'./plots/analysis/{self.dates[i * nim]}_{self.dates[(i + 1) * nim - 1]}.png')

    def plot_cluster_leads_error(self):
        no_cyc, cyc, cyc_prior, no_cyc_prior = self.cluster_leads(True)
        #no_cyc = np.nanstd(np.array(no_cyc), axis=0)
        #cyc = np.nanstd(np.array(cyc), axis=0)
        #cyc_prior = np.nanstd(np.array(cyc_prior), axis=0)
        #no_cyc_prior = np.nanstd(np.array(no_cyc_prior), axis=0)

        self.nrows, self.ncols = 2, 2
        fig, ([ax1, ax2], [ax3, ax4]) = self.setup_plot()

        im1 = ax1.pcolormesh(self.lon, self.lat, np.nanstd(cyc, axis=0), vmin=0, vmax=.5,
                             transform=ccrs.PlateCarree(),
                             cmap='Oranges')
        ax1.set_title('cyc (std)', fontsize=20)
        fig.colorbar(im1, ax=ax1, orientation='vertical')

        im2 = ax2.pcolormesh(self.lon, self.lat, np.nanstd(no_cyc, axis=0), vmin=0, vmax=.5,
                             transform=ccrs.PlateCarree(), cmap='Oranges')
        fig.colorbar(im2, ax=ax2, orientation='vertical')
        ax2.set_title(f'no cyc (std)', fontsize=20)

        im3 = ax3.pcolormesh(self.lon, self.lat, np.nanstd(cyc_prior, axis=0), vmin=0, vmax=.5,
                             transform=ccrs.PlateCarree(),
                             cmap='Oranges')
        ax3.set_title('cyc prior (std)', fontsize=20)
        fig.colorbar(im3, ax=ax3, orientation='vertical')

        im4 = ax4.pcolormesh(self.lon, self.lat, np.nanstd(no_cyc_prior, axis=0), vmin=0, vmax=.5,
                             transform=ccrs.PlateCarree(), cmap='Oranges')
        fig.colorbar(im4, ax=ax4, orientation='vertical')
        ax4.set_title(f'no cyc prior (std)', fontsize=20)

        plt.tight_layout()
        plt.savefig(f'./plots/analysis/clustered_leads_std_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

    def plot_clustered_leads(self, from_pickle=False):
        self.nrows, self.ncols = 2, 3
        if from_pickle:
            with open(f'./pickles/clustered_leads_{self.sic_filter}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}.pkl', 'rb') as pickle_in:
                no_cyc, cyc, cyc_prior, no_cyc_prior = pickle.load(pickle_in)
                print(no_cyc.shape)
                no_cyc, cyc = np.nanmean(no_cyc, axis=0), np.nanmean(cyc, axis=0)
                cyc_prior, no_cyc_prior = np.nanmean(cyc_prior, axis=0), np.nanmean(no_cyc_prior, axis=0)
        else:
            no_cyc, cyc, cyc_prior, no_cyc_prior = self.cluster_leads()

        fig, axs = self.setup_plot()
        ax1, ax2, ax3, ax4, ax5, ax6 = axs[0, 0], axs[0, 1], axs[1, 0], axs[1, 1], axs[0, 2], axs[1, 2]

        im1 = ax1.pcolormesh(self.lon, self.lat, no_cyc, vmin=0, vmax=1, transform=ccrs.PlateCarree())
        ax1.set_title('no cyc', fontsize=20)

        im2 = ax2.pcolormesh(self.lon, self.lat, cyc, vmin=0, vmax=1, transform=ccrs.PlateCarree())
        ax2.set_title('cyc', fontsize=20)
        fig.colorbar(im2, ax=ax2, orientation='vertical')

        im5 = ax5.pcolormesh(self.lon, self.lat, cyc - no_cyc, vmin=-.1, vmax=.1, transform=ccrs.PlateCarree(),
                             cmap='bwr')
        ax5.set_title('cyc - no cyc', fontsize=20)
        fig.colorbar(im5, ax=ax5, orientation='vertical')

        im4 = ax4.pcolormesh(self.lon, self.lat, cyc_prior, vmin=0, vmax=1, transform=ccrs.PlateCarree())
        ax4.set_title(f'cyc prior {self.delta_days}', fontsize=20)
        fig.colorbar(im4, ax=ax4, orientation='vertical')

        im3 = ax3.pcolormesh(self.lon, self.lat, no_cyc_prior, vmin=0, vmax=1, transform=ccrs.PlateCarree())
        ax3.set_title(f'no cyc prior {self.delta_days}', fontsize=20)

        im6 = ax6.pcolormesh(self.lon, self.lat, cyc_prior - no_cyc_prior, vmin=-.1, vmax=.1,
                             transform=ccrs.PlateCarree(), cmap='bwr')
        fig.colorbar(im6, ax=ax6, orientation='vertical')
        ax6.set_title(f'cyc prior - no cyc prior', fontsize=20)

        plt.tight_layout()
        plt.savefig(f'./plots/analysis/deep time/clustered_leads_sicfilter{int(self.sic_filter)}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

    def plot_clustered_div_significant(self, from_pickle=False):
        path = f'./pickles/clustered_leads_m3d=True_True_{self.sic_filter}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}.pkl'
        print(path)
        if from_pickle:
            with open(path, 'rb') as pickle_in:
                no_cyc, cyc, cyc_prior, no_cyc_prior, no_cyc_div, cyc_div = pickle.load(pickle_in)

        else:
            no_cyc, cyc, cyc_prior, no_cyc_prior, no_cyc_div, cyc_div = self.cluster_leads()

        # perform T-test on divergence data cyclone vs. no cyclone
        ttest = ttest_ind(cyc_div, no_cyc_div, nan_policy='omit', equal_var=False, axis=0)
        pvalues, statistics = ttest.__getattribute__('pvalue'), ttest.__getattribute__('statistic')
        print(cyc_div.shape)

        self.nrows, self.ncols = 1, 2
        fig, (ax1, ax2) = self.setup_plot()

        im1 = ax1.pcolormesh(self.lon, self.lat, statistics, transform=ccrs.PlateCarree(),
                             cmap='coolwarm')
        ax1.set_title(f'T-test', fontsize=20)
        fig.colorbar(im1, ax=ax1)

        im2 = ax2.pcolormesh(self.lon, self.lat, pvalues, vmin=0., vmax=1., transform=ccrs.PlateCarree())
        ax2.set_title(f'p-values', fontsize=20)
        fig.colorbar(im2, ax=ax2)

        plt.tight_layout()
        plt.savefig(
            f'./plots/analysis/significancy_div_{int(self.sic_filter)}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

        # plot only the significant results
        cyc_div, no_cyc_div = np.nanmean(np.array(cyc_div), axis=0), np.nanmean(np.array(no_cyc_div), axis=0)
        diff = cyc_div - no_cyc_div
        self.nrows, self.ncols = 1, 1
        fig, ax = self.setup_plot()
        diff[pvalues >= .2] = np.nan
        im1 = ax.pcolormesh(self.lon, self.lat, diff, vmin=-3.e-7, vmax=3.e-7, transform=ccrs.PlateCarree(), cmap='coolwarm')
        ax.set_title(f'ice divergence, cyc - no cyc, values with p < 0.2', fontsize=20)
        fig.colorbar(im1, ax=ax)
        plt.tight_layout()
        plt.savefig(
            f'./plots/analysis/signif_res_div_{int(self.sic_filter)}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

    def plot_clustered_leads_div(self, from_pickle=False):
        self.nrows, self.ncols = 1, 3
        if from_pickle:
            with open(
                    f'./pickles/clustered_leads_{self.collect_ice_div}_{self.sic_filter}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}.pkl',
                    'rb') as pickle_in:
                no_cyc, cyc, cyc_prior, no_cyc_prior, no_cyc_div, cyc_div = pickle.load(pickle_in)

        else:
            no_cyc, cyc, cyc_prior, no_cyc_prior, no_cyc_div, cyc_div = self.cluster_leads()

        fig, (ax1, ax2, ax3) = self.setup_plot()

        im1 = ax1.pcolormesh(self.lon, self.lat, np.nanmean(self.divs, axis=0), vmin=-6.e-07, vmax=6.e-07,
                             transform=ccrs.PlateCarree(), cmap='bwr')
        ax1.set_title('ice divergence', fontsize=20)
        fig.colorbar(im1, ax=ax1, orientation='vertical', fraction=0.046, pad=0.04)

        im2 = ax2.pcolormesh(self.lon, self.lat, np.ones(shape=self.lat.shape), transform=ccrs.PlateCarree())
        ax2.set_title(f'wind divergence (not finished)', fontsize=20)
        fig.colorbar(im2, ax=ax2, orientation='vertical', fraction=0.046, pad=0.04)

        im3 = ax3.pcolormesh(self.lon, self.lat, cyc_prior - no_cyc_prior, vmin=-.1, vmax=.1,
                             transform=ccrs.PlateCarree(), cmap='bwr')
        fig.colorbar(im3, ax=ax3, orientation='vertical', fraction=0.046, pad=0.04)
        ax3.set_title(f'cyc prior - no cyc prior', fontsize=20)

        plt.savefig('./plots/clustered_divergence_test')

    def plot_clustered_leads_clustered_div(self, from_pickle=False):
        self.nrows, self.ncols = 1, 3
        if from_pickle:
            with open(
                    f'./pickles/clustered_leads_{self.collect_ice_div}_{self.sic_filter}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}.pkl',
                    'rb') as pickle_in:
                no_cyc, cyc, cyc_prior, no_cyc_prior, no_cyc_div, cyc_div = pickle.load(pickle_in)

        else:
            no_cyc, cyc, cyc_prior, no_cyc_prior, no_cyc_div, cyc_div = self.cluster_leads()

        fig, (ax1, ax2, ax3) = self.setup_plot()

        im1 = ax1.pcolormesh(self.lon, self.lat, no_cyc_div, vmin=-3.e-07, vmax=3.e-07,
                             transform=ccrs.PlateCarree(), cmap='bwr')
        ax1.set_title('ice divergence while NO cyc', fontsize=20)
        fig.colorbar(im1, ax=ax1, orientation='vertical', fraction=0.046, pad=0.04)

        im2 = ax2.pcolormesh(self.lon, self.lat, cyc_div, vmin=-3.e-07, vmax=3.e-07, transform=ccrs.PlateCarree(), cmap='bwr')
        ax2.set_title(f'ice divergence while cyc', fontsize=20)
        fig.colorbar(im2, ax=ax2, orientation='vertical', fraction=0.046, pad=0.04)

        im3 = ax3.pcolormesh(self.lon, self.lat, cyc_div - no_cyc_div, vmin=-3.e-07, vmax=3.e-07,
                             transform=ccrs.PlateCarree(), cmap='bwr')
        fig.colorbar(im3, ax=ax3, orientation='vertical', fraction=0.046, pad=0.04)
        ax3.set_title(f'cyc - no_cyc', fontsize=20)

        plt.tight_layout()
        plt.savefig(
            f'./plots/analysis/deep time/clustered_leads_clustered_div_sicfilter{int(self.sic_filter)}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

    def compare_deltadays(self):
        img = []
        for i in range(1, 7):
            print(i)
            self.leads, self.cycs, self.cycs_past = [], [], []
            self.delta_days = i
            _, _, cyc_prior, no_cyc_prior, _, _ = self.cluster_leads()
            img.append(cyc_prior - no_cyc_prior)
        # img = np.array(img)

        '''for i in range(len(img) - 1):
            print(i)
            diff.append(np.absolute(img[i+1] - img[i]))

        diff = np.array(diff)
        vcap = np.nanmax(diff) -.3
        print(vcap)
        self.nrows, self.ncols = 2, 3'''
        self.nrows, self.ncols = 2, 3
        fig, axs = self.setup_plot()
        for i, ax in enumerate(axs.flatten()):
            print(i)
            im = ax.pcolormesh(self.lon, self.lat, img[i], transform=ccrs.PlateCarree(), cmap='bwr', vmin=-.1, vmax=.1)
            ax.set_title(f'Delta d = {i + 1}')

            fig.colorbar(im, ax=ax)
        plt.tight_layout()
        plt.savefig(f'./plots/analysis/compare_deltad_{self.dates[0]}_{self.dates[-1]}')

    def compare_deltadays_graph(self):
        fig, ax = plt.subplots()
        ax.set_xlabel('days prior')
        ax.set_ylabel('mean difference to days prior = 0')
        for i in range(0, 7):
            print(i)
            self.leads, self.cycs, self.cycs_past = [], [], []
            self.delta_days = i
            no_cyc, cyc, cyc_prior, no_cyc_prior = self.cluster_leads()

            diff = cyc_prior - no_cyc_prior - (cyc - no_cyc)
            ax.scatter(i, np.nanmean(diff), c='steelblue')

        plt.tight_layout()
        plt.savefig(f'./plots/analysis/compare_deltad_graph_{self.dates[0]}_{self.dates[-1]}')

    def plot_average_cyc_lead(self):
        self.collect_leads_cycs()
        self.cycs = np.array(self.cycs)
        self.leads = np.array(self.leads)
        self.cycs[np.isnan(self.cycs)] = 0

        mean_l, mean_c = np.nanmean(self.leads, axis=0), np.nanmean(self.cycs, axis=0)
        self.nrows, self.ncols = 1, 2
        fig, ax = self.setup_plot()

        im1 = ax[0].pcolormesh(self.lon, self.lat, mean_l, transform=ccrs.PlateCarree())
        ax[0].set_title(f'Avg lead fraction {self.dates[0]}/{self.dates[- 1]}', fontsize=20)
        fig.colorbar(im1, ax=ax[0], orientation='horizontal')

        im2 = ax[1].pcolormesh(self.lon, self.lat, mean_c, transform=ccrs.PlateCarree())
        ax[1].set_title(f'Avg cyc freq {self.dates[0]}/{self.dates[- 1]}', fontsize=20)
        fig.colorbar(im2, ax=ax[1], orientation='horizontal')

        plt.tight_layout()
        plt.savefig(f'./plots/analysis/avg_{self.dates[0]}_{self.dates[- 1]}.png')

    def plot_ndata(self):
        self.leads, self.cycs, self.cycs_past = [], [], []
        _, _, cyc_prior, no_cyc_prior = self.cluster_leads(matrix3d=True)
        ndata_cyc = np.zeros(cyc_prior[0].shape)
        ndata_ncyc = np.zeros(cyc_prior[0].shape)

        for cp, ncp in zip(cyc_prior, no_cyc_prior):
            ccp, cncp = np.copy(cp), np.copy(ncp)
            ccp[np.isnan(cp)] = 0
            ccp[~np.isnan(cp)] = 1
            cncp[np.isnan(ncp)] = 0
            cncp[~np.isnan(ncp)] = 1

            ndata_cyc += ccp
            ndata_ncyc += cncp

        self.nrows, self.ncols = 1, 2
        fig, (ax1, ax2) = self.setup_plot()

        im1 = ax1.pcolormesh(self.lon, self.lat, ndata_ncyc, vmax=100, transform=ccrs.PlateCarree())
        ax1.set_title(f'number of data points no cyc dates', fontsize=20)
        fig.colorbar(im1, ax=ax1)

        im2 = ax2.pcolormesh(self.lon, self.lat, ndata_cyc, vmax=100, transform=ccrs.PlateCarree())
        ax2.set_title(f'number of data points cyc dates', fontsize=20)
        fig.colorbar(im2, ax=ax2)

        plt.tight_layout()
        plt.savefig(
            f'./plots/analysis/ndata_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

    def significance_test(self):
        path = f'./pickles/clustered_leads_m3d=True_True_{self.sic_filter}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}.pkl'
        print(path)
        with open(path, 'rb') as pickle_in:
            _, _, cyc_prior, no_cyc_prior = pickle.load(pickle_in)

        print(cyc_prior.shape, no_cyc_prior.shape)
        ttest = ttest_ind(cyc_prior, no_cyc_prior, nan_policy='omit', equal_var=False, axis=0)
        pvalues, statistics = ttest.__getattribute__('pvalue'), ttest.__getattribute__('statistic')
        print(statistics.shape)

        self.nrows, self.ncols = 1, 2
        fig, (ax1, ax2) = self.setup_plot()

        im1 = ax1.pcolormesh(self.lon, self.lat, statistics, vmax=10, vmin=-10, transform=ccrs.PlateCarree(), cmap='coolwarm')
        ax1.set_title(f'T-test', fontsize=20)
        fig.colorbar(im1, ax=ax1)

        im2 = ax2.pcolormesh(self.lon, self.lat, pvalues, vmax=1., transform=ccrs.PlateCarree(), cmap='gray')
        ax2.set_title(f'p-values', fontsize=20)
        fig.colorbar(im2, ax=ax2)

        plt.tight_layout()
        plt.savefig(f'./plots/analysis/significancy_{int(self.sic_filter)}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

        # plot only the significant results
        cyc_prior, no_cyc_prior = np.nanmean(np.array(cyc_prior), axis=0), np.nanmean(np.array(no_cyc_prior), axis=0)
        diff = cyc_prior - no_cyc_prior
        self.nrows, self.ncols = 1, 1
        fig, ax = self.setup_plot()
        diff[pvalues >= .1] = np.nan
        im1 = ax.pcolormesh(self.lon, self.lat, diff, transform=ccrs.PlateCarree(), vmin=-.1, vmax=.1, cmap='coolwarm')
        ax1.set_title(f'T-test', fontsize=20)
        fig.colorbar(im1, ax=ax)
        plt.tight_layout()
        plt.savefig(
            f'./plots/analysis/signif_res_{int(self.sic_filter)}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

    def difference_time_window_sig(self):
        with open(f'./pickles/clustered_leads_{self.sic_filter}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}.pkl',
                  'rb') as pickle_in:
            _, _, cyc_prior, no_cyc_prior = pickle.load(pickle_in)

        regime_shift_ind = int(cyc_prior.shape[0] / 2)

        for mat, title in zip([cyc_prior, no_cyc_prior], ['cyc', 'no_cyc']):
            ttest = ttest_ind(mat[:regime_shift_ind], mat[regime_shift_ind:], nan_policy='omit', equal_var=False)
            pvalues, statistics = ttest.__getattribute__('pvalue'), ttest.__getattribute__('statistic')
            print(statistics.reshape(self.lon.shape))

            self.nrows, self.ncols = 1, 2
            fig, (ax1, ax2) = self.setup_plot()

            im1 = ax1.pcolormesh(self.lon, self.lat, statistics, vmax=10, vmin=-10, transform=ccrs.PlateCarree(),
                                 cmap='coolwarm')
            ax1.set_title(f'T-test', fontsize=20)
            fig.colorbar(im1, ax=ax1)

            im2 = ax2.pcolormesh(self.lon, self.lat, pvalues, vmax=1., transform=ccrs.PlateCarree(), cmap='gray')
            ax2.set_title(f'p-values', fontsize=20)
            fig.colorbar(im2, ax=ax2)

            plt.tight_layout()
            plt.savefig(
                f'./plots/analysis/timesplit_{title}_{int(self.sic_filter)}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

            # plot only the significant results
            diff1, diff2 = np.nanmean(np.array(mat[:regime_shift_ind]), axis=0), np.nanmean(np.array(mat[regime_shift_ind:]), axis=0)
            diff = diff2 - diff1
            self.nrows, self.ncols = 1, 1
            fig, ax = self.setup_plot()
            diff[pvalues >= .1] = np.nan
            im1 = ax.pcolormesh(self.lon, self.lat, diff, transform=ccrs.PlateCarree(), vmin=-.1, vmax=.1, cmap='coolwarm')
            ax1.set_title(f'T-test', fontsize=20)
            fig.colorbar(im1, ax=ax)
            plt.tight_layout()
            plt.savefig(
                f'./plots/analysis/timesplit_diff_{title}_{int(self.sic_filter)}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

    def difference_time_window(self):
        with open(f'./pickles/clustered_leads_{self.sic_filter}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}.pkl',
                  'rb') as pickle_in:
            _, _, cyc_prior, no_cyc_prior = pickle.load(pickle_in)

        regime_shift_ind = int(cyc_prior.shape[0] / 2)
        cyc_prior1, cyc_prior2 = np.nanmean(cyc_prior[:regime_shift_ind], axis=0), np.nanmean(cyc_prior[regime_shift_ind:], axis=0)
        no_cyc_prior1, no_cyc_prior2 = np.nanmean(no_cyc_prior[:regime_shift_ind], axis=0), np.nanmean(no_cyc_prior[regime_shift_ind:], axis=0)

        diff_cyc = cyc_prior2 - cyc_prior1
        diff_no_cyc = no_cyc_prior2 - no_cyc_prior1

        print(diff_cyc.shape)

        self.nrows, self.ncols = 1, 2
        fig, (ax1, ax2) = self.setup_plot()
        ax1.pcolormesh(self.lon, self.lat, diff_cyc, transform=ccrs.PlateCarree(), vmin=-.1, vmax=.1, cmap='coolwarm')
        ax2.pcolormesh(self.lon, self.lat, diff_no_cyc, transform=ccrs.PlateCarree(), vmin=-.1, vmax=.1, cmap='coolwarm')
        plt.tight_layout()
        plt.savefig(
            f'./plots/analysis/timesplit_diff_{int(self.sic_filter)}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}')

    def climatology(self):
        # collect data
        try:
            with open(f'./pickles/collections_{self.sic_filter}_{self.dates[0]}_{self.dates[-1]}.pkl', 'rb') as pickle_in:
                print('Try to import collection')
                self.leads, self.cycs = pickle.load(pickle_in)
                print('done')
        except FileNotFoundError:
            print('could not find collection \n try to create collection and restart')
            self.export_collection()
            print('done')
            self.climatology()
            return 'Finished with exception'

        # transform to numpy array
        self.leads, self.cycs = np.array(self.leads), np.array(self.cycs)
        N, M = 100, 150
        lon, lat = round(self.lon[N, M]), round(self.lat[N, M])

        fig, axs = plt.subplots(4, 1, figsize=(15, 7))

        for ax in axs.flatten():
            N, M = np.random.randint(100, 200), np.random.randint(100, 200)
            lon, lat = round(self.lon[N, M]), round(self.lat[N, M])

            ax.set_title(f'lon: {lon}, lat: {lat}')
            n_Time = 175
            ax.bar(ds.string_time_to_datetime(self.dates)[:n_Time], self.leads[:n_Time, N, M])

        plt.tight_layout()
        plt.savefig('climatology_test2.png')

    def leads_div_npoints(self, from_pickle):
        path = f'./pickles/clustered_leads_m3d=True_{self.collect_ice_div}_{self.sic_filter}_{self.delta_days}_{self.dates[0]}_{self.dates[-1]}.pkl'
        if from_pickle:
            with open(path, 'rb') as pickle_in:
                no_cyc, cyc, cyc_prior, no_cyc_prior, no_cyc_div, cyc_div = pickle.load(pickle_in)

        else:
            no_cyc, cyc, cyc_prior, no_cyc_prior, no_cyc_div, cyc_div = self.cluster_leads()

        self.nrows, self.ncols = 2, 2
        fig, axs = self.setup_plot()
        axs = axs.flatten()

        titles = ['leads cyc', 'leads NO cyc', 'div cyc', 'div NO cyc']

        for ax, title, data in zip(axs, titles, [cyc_prior, no_cyc_prior, cyc_div, no_cyc_div]):
            im = ax.pcolormesh(self.lon, self.lat, np.sum(~np.isnan(data), axis=0), vmin=0, vmax=1000, transform=ccrs.PlateCarree())
            cbar = fig.colorbar(im, ax=ax)
            cbar.ax.tick_params(labelsize=20)
            ax.set_title(title, fontsize=20)



        plt.tight_layout()
        plt.savefig('./plots/analysis/n_points.png')


def multi_year_average_lead_cyc(mean='day', plot=True):
    dates = ds.time_delta('20021101', '20151231')
    dt_dates = ds.string_time_to_datetime(dates)
    lead_data, cyc_data, time = [], [], []

    for date in dates:
        ds_obj = leads.LeadAllY(date)
        lead_data.append(ds_obj.lead_data)
        cyc_data.append(ds_obj.cyc_data)

    cyc_data, lead_data = np.array(cyc_data), np.array(lead_data)
    if mean == 'day':
        print('h')
        mean_cyc = []
        mean_lead = []

        for lead, cyc in zip(lead_data, cyc_data):
            mean_cyc.append(np.nanmean(cyc))
            mean_lead.append(np.nanmean(lead))

        time = dt_dates

    elif mean == 'month':
        mean_cyc, current_cyc = [], []
        mean_lead, current_lead = [], []
        prev_month = dt_dates[0].month

        for lead, cyc, date in zip(lead_data, cyc_data, dt_dates):
            month = date.month

            if month == prev_month:
                current_cyc.append(cyc)
                current_lead.append(lead)
            else:
                mean_cyc.append(np.nanmean(current_cyc))
                mean_lead.append(np.nanmean(current_lead))
                time.append(f'{date.year - 2000}/{date.month}')

                current_cyc, current_lead = [], []

            prev_month = month

    if plot:
        # mean_lead, mean_cyc, time = multy_year_average_lead_cyc(mean='month')
        fig, (ax1, ax2) = plt.subplots(2)
        ax1.scatter(time, mean_lead, label='lead', c='orange', alpha=.1)
        ax2.scatter(time, mean_cyc, label='cyc', alpha=.1)
        ax1.legend()
        ax2.legend()
        fig.autofmt_xdate()

        skip = 6
        ax2.set_xticks(time[::skip])
        ax2.set_xticklabels(time[::skip], rotation=45)
        ax1.set_xticks(time[::skip])
        ax1.set_xticklabels(time[::skip], rotation=45)
        ax1.set_title('monthly mean of lead fraction/cyc occurence over time')
        # plt.show()
        fig.tight_layout()
        plt.savefig(f'./mean_{mean}_lead_cyc.png')
        print('done')

    return mean_lead, mean_cyc, time


if __name__ == '__main__':
    # A = Analysis('20200217', '20200224')
    # A = Analysis('20021105', '20190430', collect_ice_div=False)
    # A.plot_average_cyc_lead()
    # A = Analysis('20191105', '20191130')
    # A = Analysis('20100105', '20110215')
    A = Analysis('20140105', '20191229')
    # A.delta_days = 2
    # A = Analysis('20180101', '20190429')
    # A.plot_clustered_leads_div()
    # A.export_clustered_leads(True)
    # A.plot_clustered_leads_div(False)
    # A.compare_deltadays()
    # A.significance_test()
    # A.plot_clustered_div_significant(True)
    A.leads_div_npoints(True)

    # A.delta_days = 3
    # A.plot_clustered_leads(True)
    # A.plot()
    # A.export_clustered_leads(True)
    # A.significance_test()
    # A.difference_time_window()

    '''for i in range(0, 9):
        A = Analysis(f'201{i}1105', f'201{i+1}0430')
        A.plot_clustered_leads()
    '''
    # multi_year_average_lead_cyc(mean='day')

    arr = np.array([[[np.nan, 2, 3, 4], [1, 2, np.nan, 4], [1, 2, 3, 4]], [[np.nan, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4]]])
    print(np.sum(~np.isnan(arr), axis=0))

    pass

