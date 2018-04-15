import os
import csv
import numpy as np
import pandas as pd
import nibabel as nib
from sklearn.svm import SVR
import matplotlib.pyplot as plt
from aux_process import *
import pickle
import seaborn as sns
import matplotlib.ticker as ticker
from pylab import pcolor, show, colorbar
from sklearn.metrics import mean_squared_error, r2_score

from datetime import datetime

from sklearn import svm
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.metrics import confusion_matrix, roc_curve, auc

from scipy.stats import ttest_rel
from scipy.stats import pearsonr
from sklearn.metrics import mean_squared_error

from joblib import Parallel, delayed

########################################################################################################################

monitor_width = 1680
monitor_height = 1050

# eye_mask = nib.load('/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_eye_mask.nii.gz')
eye_mask = nib.load('/data2/Projects/Jake/eye_masks/2mm_eye_corrected.nii.gz')
eye_mask = eye_mask.get_data()
resample_path = '/data2/Projects/Jake/Human_Brain_Mapping/'
eye_tracking_path = '/data2/HBN/EEG/data_RandID/'
hbm_path = '/data2/Projects/Jake/Human_Brain_Mapping/'


def load_data(min_scan=2):

    """Returns list of subjects with at least the specified number of calibration scans

    :param min_scan: Minimum number of scans required to be included in subject list
    :return: Dataframe containing subject IDs, site of MRI collection, number of calibration scans, and motion measures
    :return: List containing subjects with at least min_scan calibration scans
    """

    params = pd.read_csv('model_outputs.csv', index_col='subject', dtype=object)
    params = params.convert_objects(convert_numeric=True)

    if min_scan == 2:

        params = params[(params.scan_count == 2) | (params.scan_count == 3)]

    elif min_scan == 3:

        params = params[params.scan_count == 3]

    sub_list = params.index.values.tolist()

    return params, sub_list


def train_model(sub, train_file, test_file, gsr_status, viewtype):
    """ Trains and creates model based on specified calibration scans

    :param sub: Subject ID
    :param train_file: List that contains calibration scans for training
    :param test_file: String that contains name of calibration scan for testing
    :param gsr_status: Whether or not to use GSR
    :param viewtype: Viewing stimulus
    :return: x_error_sk, the RMSE in the x-direction
    :return: y_error_sk, the RMSE in the y-direction
    :return: x_corr, the Pearson correlation value in the x-direction
    :return: y_corr, the Pearson correlation value in the y-direction
    :return: predicted_x, list containing predicted fixations in the x-direction
    :return: predicted_y, list containing predicted fixations in the y-direction
    :return: x_model, SVM model in the x-direction
    :return: y_model, SVM model in the y-direction
    """

    fixations = pd.read_csv('stim_vals.csv')
    x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 1) * monitor_width / 2, len(train_file))
    y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 1) * monitor_height / 2, len(train_file))

    if len(train_file) == 2:

        scan1 = nib.load(resample_path + sub + train_file[0])
        scan2 = nib.load(resample_path + sub + test_file)
        scan3 = nib.load(resample_path + sub + train_file[1])

        scan1 = scan1.get_data()
        scan2 = scan2.get_data()
        scan3 = scan3.get_data()

        for item in [scan1, scan2, scan3]:

            for vol in range(item.shape[3]):
                output = np.multiply(eye_mask, item[:, :, :, vol])

                item[:, :, :, vol] = output

        for item in [scan1, scan2, scan3]:
            item = mean_center_var_norm(item)
            if gsr_status == 1:
                item = gs_regress(item, eye_mask)

        listed1 = []
        listed2 = []
        listed_testing = []

        print('beginning vectors')

        for tr in range(int(scan1.shape[3])):
            tr_data1 = scan1[:, :, :, tr]
            vectorized1 = np.array(tr_data1.ravel())
            listed1.append(vectorized1)

            tr_data2 = scan3[:, :, :, tr]
            vectorized2 = np.array(tr_data2.ravel())
            listed2.append(vectorized2)

        for tr in range(int(scan2.shape[3])):
            te_data = scan2[:, :, :, tr]
            vectorized_testing = np.array(te_data.ravel())
            listed_testing.append(vectorized_testing)

        train_vectors1 = np.asarray(listed1)
        test_vectors = np.asarray(listed_testing)
        train_vectors2 = np.asarray(listed2)

        train_vectors = data_processing(3, train_vectors1, train_vectors2)


    elif len(train_file) == 1:

        scan1 = nib.load(resample_path + sub + train_file[0])
        scan2 = nib.load(resample_path + sub + test_file)

        scan1 = scan1.get_data()
        scan2 = scan2.get_data()

        for item in [scan1, scan2]:

            for vol in range(item.shape[3]):
                output = np.multiply(eye_mask, item[:, :, :, vol])

                item[:, :, :, vol] = output

        for item in [scan1, scan2]:
            item = mean_center_var_norm(item)
            if gsr_status == 1:
                item = gs_regress(item, eye_mask)

        listed1 = []
        listed_testing = []

        print('beginning vectors')

        for tr in range(int(scan1.shape[3])):
            tr_data1 = scan1[:, :, :, tr]
            vectorized1 = np.array(tr_data1.ravel())
            listed1.append(vectorized1)

        for tr in range(int(scan2.shape[3])):
            te_data = scan2[:, :, :, tr]
            vectorized_testing = np.array(te_data.ravel())
            listed_testing.append(vectorized_testing)

        train_vectors1 = np.asarray(listed1)
        test_vectors = np.asarray(listed_testing)

        train_vectors2 = []

        train_vectors = data_processing(2, train_vectors1, train_vectors2)

    x_model, y_model = create_model(train_vectors, x_targets, y_targets)
    print('Finished creating model')

    predicted_x, predicted_y = predict_fixations(x_model, y_model, test_vectors)
    predicted_x = np.array([np.round(float(x), 3) for x in predicted_x])
    predicted_y = np.array([np.round(float(x), 3) for x in predicted_y])

    x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 5) * monitor_width / 2, 1)
    y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 5) * monitor_height / 2, 1)

    if viewtype == 'calibration':

        x_corr = pearsonr(predicted_x, x_targets)[0]
        y_corr = pearsonr(predicted_y, y_targets)[0]

        x_error_sk = np.sqrt(mean_squared_error(predicted_x, x_targets))
        y_error_sk = np.sqrt(mean_squared_error(predicted_y, y_targets))

        print('Finished calculating parameters')

    return x_error_sk, y_error_sk, x_corr, y_corr, predicted_x, predicted_y, x_model, y_model


def load_model(sub, test_file, gsr_status):

    """Loads pre-existing model to predict fixations from new fMRI data

    :param sub: Subject ID
    :param test_file: String that contains name of calibration scan for testing
    :param gsr_status: Whether or not to use GSR
    :return: predicted_x, list containing predicted fixations in the x-direction
    :return: predicted_y, list containing predicted fixations in the y-direction
    """

    print('Load model')

    scan2 = nib.load(resample_path + sub + test_file)
    scan2 = scan2.get_data()
    print('Scan 2 loaded')

    print('Applying eye-mask')

    for item in [scan2]:

        for vol in range(item.shape[3]):
            output = np.multiply(eye_mask, item[:, :, :, vol])

            item[:, :, :, vol] = output

    print('Applying mean-centering with variance-normalization and GSR')

    scan2 = mean_center_var_norm(scan2)

    if gsr_status == 1:

        scan2 = gs_regress(scan2, eye_mask)

    listed_testing = []

    print('beginning vectors')

    for tr in range(int(scan2.shape[3])):
        te_data = scan2[:, :, :, tr]
        vectorized_testing = np.array(te_data.ravel())
        listed_testing.append(vectorized_testing)

    test_vectors = np.asarray(listed_testing)

    x_model = pickle.load(open('/data2/Projects/Jake/Human_Brain_Mapping/' + str(sub) + '/x_gsr0_train1_model.sav', 'rb'))
    y_model = pickle.load(open('/data2/Projects/Jake/Human_Brain_Mapping/' + str(sub) + '/y_gsr0_train1_model.sav', 'rb'))

    ###################################

    predicted_x, predicted_y = predict_fixations(x_model, y_model, test_vectors)
    predicted_x = np.array([np.round(float(x), 3) for x in predicted_x])
    predicted_y = np.array([np.round(float(x), 3) for x in predicted_y])

    return predicted_x, predicted_y


def save_models(sub, viewtype, x_corr, y_corr, x_error_sk, y_error_sk, predicted_x, predicted_y,
                x_model, y_model, model_save_name, predictions_save_name, parameters_save_name):

    """

    :param sub: Subject ID
    :param viewtype: Viewing stimulus
    :param x_corr: the Pearson correlation value in the x-direction
    :param y_corr: the Pearson correlation value in the y-direction
    :param x_error_sk: the RMSE in the x-direction
    :param y_error_sk: the RMSE in the y-direction
    :param predicted_x: list containing predicted fixations in the x-direction
    :param predicted_y: list containing predicted fixations in the y-direction
    :param x_model: SVM model in the x-direction
    :param y_model: SVM model in the y-direction
    :param model_save_name: Filename for SVM models
    :param predictions_save_name: Filename for predictions in x- and y- directions
    :param parameters_save_name: Filename for error measures from calibration scans
    """

    print('Updating output for subject ' + str(sub))

    param_dict = {'sub': [sub, sub], 'corr_x': [], 'corr_y': [], 'rmse_x': [], 'rmse_y': []}
    output_dict = {'x_pred': [], 'y_pred': []}

    if viewtype == 'calibration':

        param_dict['corr_x'] = x_corr
        param_dict['corr_y'] = y_corr
        param_dict['rmse_x'] = x_error_sk
        param_dict['rmse_y'] = y_error_sk
        output_dict['x_pred'] = predicted_x
        output_dict['y_pred'] = predicted_y

        df_p = pd.DataFrame(param_dict)
        df_p.to_csv('/data2/Projects/Jake/Human_Brain_Mapping/' + str(sub) + '/' + parameters_save_name)
        df_o = pd.DataFrame(output_dict)
        df_o.to_csv('/data2/Projects/Jake/Human_Brain_Mapping/' + str(sub) + '/' + predictions_save_name)

        pickle.dump(x_model, open('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/x_' + model_save_name, 'wb'))
        pickle.dump(y_model, open('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/y_' + model_save_name, 'wb'))


def save_predictions(sub, predicted_x, predicted_y, predictions_save_name):

    """Saves prediction series as csv

    :param sub: Subject ID
    :param predicted_x: list containing predicted fixations in the x-direction
    :param predicted_y: list containing predicted fixations in the y-direction
    :param predictions_save_name: Filename for predictions in x- and y- directions
    """

    output_dict = {'x_pred': [], 'y_pred': []}

    output_dict['x_pred'] = predicted_x
    output_dict['y_pred'] = predicted_y

    df_o = pd.DataFrame(output_dict)
    df_o.to_csv('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/' + predictions_save_name)


def peer_hbm(sub, viewtype='calibration', gsr_status=False, train_set='1'):

    """Creates models and saves predictions and measures of fit (correlation, RMSE)

    :param sub: Subject ID
    :param viewtype: Viewing stimulus
    :param gsr_status: Whether or not to use GSR
    :param train_set: Specifies the set of calibration scans used for training
    """

    print('Starting with participant ' + str(sub) + ' for viewing ' + str(viewtype))

    model_type = {'calibration': {'1': {'train': ['/peer1_eyes_sub.nii.gz'], 'test': '/peer2_eyes_sub.nii.gz'},
                                  '3': {'train': ['/peer3_eyes_sub.nii.gz'], 'test': '/peer2_eyes_sub.nii.gz'},
                                  '13': {'train': ['/peer1_eyes_sub.nii.gz', '/peer3_eyes_sub.nii.gz'],
                                         'test': '/peer2_eyes_sub.nii.gz'}},
                  'tp': {'1': {'test': '/movie_TP_eyes_sub.nii.gz'}},
                  'dm': {'1': {'test': '/movie_DM_eyes_sub.nii.gz'}}}

    try:

        gsr_status = int(gsr_status)
        test_file = model_type[viewtype][train_set]['test']

        if viewtype == 'calibration':
            train_file = model_type[viewtype][train_set]['train']  # If train_set = '13', we have TWO training files
        else:
            train_file = ''

        model_save_name = 'gsr' + str(gsr_status) + '_train' + train_set + '_model.sav'
        predictions_save_name = model_save_name.strip('.sav') + '_' + viewtype + '_predictions.csv'
        parameters_save_name = model_save_name.strip('.sav') + '_parameters.csv'

        if (os.path.exists(resample_path + sub + '/x_' + model_save_name)) and (os.path.exists(resample_path + sub + '/y_' + model_save_name)):
            predicted_x, predicted_y = load_model(sub, test_file, gsr_status)
            save_predictions(sub, predicted_x, predicted_y, predictions_save_name)
        else:
            x_error_sk, y_error_sk, x_corr, y_corr, predicted_x, predicted_y, x_model, y_model = \
                train_model(sub, train_file, test_file, gsr_status, viewtype)
            save_models(sub, viewtype, x_corr, y_corr, x_error_sk, y_error_sk, predicted_x, predicted_y,
                        x_model, y_model, model_save_name, predictions_save_name, parameters_save_name)

    except:

        print('Error processing subject ' + str(sub))


# params, sub_list = load_data(min_scan=2)
# Parallel(n_jobs=25)(delayed(peer_hbm)(sub, viewtype='dm', gsr_status=False, train_set='1')for sub in sub_list)

def create_dict_with_rmse_and_corr_values(sub_list):

    """Creates dictionary that contains list of rmse and corr values for all training combinations

    :return: Dictionary that contains list of rmse and corr values for all training combinations
    """

    file_dict = {'1': '/gsr0_train1_model_parameters.csv',
                 '3': '/gsr0_train3_model_parameters.csv',
                 '13': '/gsr0_train13_model_parameters.csv',
                 '1gsr': '/gsr1_train1_model_parameters.csv'}

    params_dict = {'1': {'corr_x': [], 'corr_y': [], 'rmse_x': [], 'rmse_y': []},
                   '3': {'corr_x': [], 'corr_y': [], 'rmse_x': [], 'rmse_y': []},
                   '13': {'corr_x': [], 'corr_y': [], 'rmse_x': [], 'rmse_y': []},
                   '1gsr': {'corr_x': [], 'corr_y': [], 'rmse_x': [], 'rmse_y': []}}

    for sub in sub_list:

        for train_set in file_dict.keys():

            if np.isnan(pd.DataFrame.from_csv(resample_path + sub + file_dict['3'])['corr_x'][0]):

                continue

            else:

                try:

                    temp_df = pd.DataFrame.from_csv(resample_path + sub + file_dict[train_set])
                    x_corr = temp_df['corr_x'][0]
                    y_corr = temp_df['corr_y'][0]
                    x_rmse = temp_df['rmse_x'][0]
                    y_rmse = temp_df['rmse_y'][0]

                    params_dict[train_set]['corr_x'].append(x_corr)
                    params_dict[train_set]['corr_y'].append(y_corr)
                    params_dict[train_set]['rmse_x'].append(x_rmse)
                    params_dict[train_set]['rmse_y'].append(y_rmse)

                except:

                    print('Error processing subject ' + sub + ' for ' + train_set)

    return params_dict


def create_individual_swarms(sub_list, train_set='1'):

    """Create swarmplot for correlation distribution of a given training set

    :param sub_list: List of subject IDs
    :param train_set: Training set of interest
    :return: Swarm plot for correlation distributions in x- and y- directions
    """

    params_dict = create_dict_with_rmse_and_corr_values(sub_list)

    train_name = [train_set for x in range(len(params_dict[train_set]['corr_x']))]

    swarm_df = pd.DataFrame({'corr_x': params_dict[train_set]['corr_x'],
                             'corr_y': params_dict[train_set]['corr_y'],
                             'rmse_x': params_dict[train_set]['rmse_x'],
                             'rmse_y': params_dict[train_set]['rmse_y'],
                             'index': train_name})

    upper_rmse_limit = 2000

    sns.set()
    ax = sns.swarmplot(x='index', y='corr_x', data=swarm_df)
    ax.set(title='Correlation Distribution in x for Train Set ' + train_set)
    plt.ylim([-1, 1])
    plt.show()
    sns.set()
    ax = sns.swarmplot(x='index', y='corr_y', data=swarm_df)
    ax.set(title='Correlation Distribution in y for Train Set ' + train_set)
    plt.ylim([-1, 1])
    plt.show()
    sns.set()
    ax = sns.swarmplot(x='index', y='rmse_x', data=swarm_df)
    ax.set(title='RMSE Distribution in x for Train Set ' + train_set)
    plt.ylim([0, upper_rmse_limit])
    plt.show()
    sns.set()
    ax = sns.swarmplot(x='index', y='rmse_y', data=swarm_df)
    ax.set(title='RMSE Distribution in y for Train Set ' + train_set)
    plt.ylim([0, upper_rmse_limit])
    plt.show()


def stack_fixation_series(params, viewtype='calibration', sorted_by='mean_fd'):

    """ Stacks fixations for a given viewtype for heatmap visualization

    :param params: Dataframe that contains subject IDs and motion measures
    :param viewtype: Viewing stimulus
    :param sorted_by: Sort by mean_fd or dvars
    :return: Heatmap for x- and y- directions for a given viewtype
    """

    monitor_width = 1680
    monitor_height = 1050

    x_stack = []
    y_stack = []

    params = params.sort_values(by=[sorted_by])
    sub_list = params.index.values.tolist()

    filename_dict = {'calibration': {'name': '/gsr0_train1_model_calibration_predictions.csv', 'num_vol': 135},
                     'tp': {'name': '/gsr0_train1_model_tp_predictions.csv', 'num_vol': 250},
                     'dm': {'name': '/gsr0_train1_model_dm_predictions.csv', 'num_vol': 750}}

    fixations = pd.read_csv('stim_vals.csv')
    x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 5) * monitor_width / 2, 1)
    y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 5) * monitor_height / 2, 1)

    for sub in sub_list:

        try:

            temp_df = pd.DataFrame.from_csv(resample_path + sub + filename_dict[viewtype]['name'])
            x_series = list(temp_df['x_pred'])
            y_series = list(temp_df['y_pred'])

            if (len(x_series) == filename_dict[viewtype]['num_vol']) and (len(y_series) == filename_dict[viewtype]['num_vol']):

                x_series = [x if abs(x) < monitor_width/2 + .1*monitor_width else 0 for x in x_series]
                y_series = [x if abs(x) < monitor_height/2 + .1*monitor_height else 0 for x in y_series]

                x_stack.append(x_series)
                y_stack.append(y_series)

        except:

            print('Error processing subject ' + sub)

    x_hm_without_mean = np.stack(x_stack)
    y_hm_without_mean = np.stack(y_stack)

    arr = np.zeros(len(x_series))
    arrx = np.array([-np.round(monitor_width / 2, 0) for x in arr])
    arry = np.array([-np.round(monitor_height / 2, 0) for x in arr])

    if viewtype == 'calibration':

        for num in range(int(np.round(len(sub_list) * .02, 0))):
            x_stack.append(arrx)
            y_stack.append(arry)

        for num in range(int(np.round(len(sub_list) * .02, 0))):
            x_stack.append(x_targets)
            y_stack.append(y_targets)

    else:

        avg_series_x = np.mean(x_stack, axis=0)
        avg_series_y = np.mean(y_stack, axis=0)

        for num in range(int(np.round(len(sub_list) * .02, 0))):
            x_stack.append(arrx)
            y_stack.append(arry)

        for num in range(int(np.round(len(sub_list) * .02, 0))):
            x_stack.append(avg_series_x)
            y_stack.append(avg_series_y)

    x_hm = np.stack(x_stack)
    y_hm = np.stack(y_stack)

    plot_heatmap_from_stacked_fixation_series(x_hm, viewtype, direc='x')
    plot_heatmap_from_stacked_fixation_series(y_hm, viewtype, direc='y')

    return x_hm, y_hm, x_hm_without_mean, y_hm_without_mean


def compare_correlations(sub_list, x_ax='1', y_ax='13'):

    """Produces plots that compares correlation values for a given combination of training sets

    :param sub_list: List of subject IDs
    :param x_ax: Training Set 1, "independent variable"
    :param y_ax: Training Set 2, "dependent variable"
    :return:
    """

    params_dict = create_dict_with_rmse_and_corr_values(sub_list)

    val_range = np.linspace(np.nanmin(params_dict[x_ax]['corr_x']), np.nanmax(params_dict[x_ax]['corr_x']))
    z = np.polyfit(params_dict[x_ax]['corr_x'], params_dict[y_ax]['corr_x'], 1)
    p = np.poly1d(z)
    r2_text = 'r2 vale: ' + str(r2_score(params_dict[x_ax]['corr_x'], p(params_dict[x_ax]['corr_x'])))

    plt.figure()
    plt.title('Comparing training sets ' + x_ax + ' and ' + y_ax + ' in x')
    plt.xlabel('Training set ' + x_ax)
    plt.ylabel('Training set ' + y_ax)
    plt.scatter(params_dict[x_ax]['corr_x'], params_dict[y_ax]['corr_x'], label='Correlation values')
    plt.plot(val_range, z(val_range), color='r', label=r2_text)
    plt.plot([-.5, 1], [-.5, 1], '--', color='k', label='Identical Performance')
    plt.legend()
    plt.show()

    val_range = np.linspace(np.nanmin(params_dict[x_ax]['corr_x']), np.nanmax(params_dict[x_ax]['corr_x']))
    z = np.polyfit(params_dict[x_ax]['corr_x'], params_dict[y_ax]['corr_x'], 1)
    p = np.poly1d(z)
    r2_text = 'r2 vale: ' + str(r2_score(params_dict[x_ax]['corr_x'], p(params_dict[x_ax]['corr_x'])))

    plt.figure()
    plt.title('Comparing training sets ' + x_ax + ' and ' + y_ax + ' in y')
    plt.xlabel('Training set ' + x_ax)
    plt.ylabel('Training set ' + y_ax)
    plt.scatter(params_dict[x_ax]['corr_y'], params_dict[y_ax]['corr_y'], label='Correlation values')
    plt.plot(val_range, m1 * val_range + b1, color='r', label=r2_text)
    plt.plot([-.5, 1], [-.5, 1], '--', color='k', label='Identical Performance')
    plt.legend()
    plt.show()


def plot_heatmap_from_stacked_fixation_series(fixation_series, viewtype, direc='x'):

    """Plots heatmaps based on fixation series

    :param fixation_series: Numpy array containing stacked fixation series
    :param viewtype: Viewing stimulus
    :param direc: x- or y- direction specification for figure title
    :return: Heatmap of stacked fixation series
    """

    x_spacing = len(fixation_series[0])

    sns.set()
    plt.clf()
    ax = sns.heatmap(fixation_series)
    ax.set(xlabel='Volumes', ylabel='Subjects')
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
    ax.xaxis.set_major_locator(ticker.MultipleLocator(base=np.round(x_spacing/5, 0)))
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(base=100))
    plt.title('Fixation Series for ' + viewtype + ' in ' + direc)
    plt.show()



def motion_and_correlation_linear_fit(sub_list, motion_type='mean_fd'):

    """Determines simple first order linear fit between motion parameter and correlation values

    :param sub_list: List of subject IDs
    :param motion_type: mean_fd or dvars
    :return: Scatter plot with first order linear fit
    """

    motion_dict = {'mean_fd': [], 'dvars': [], 'corr_x': [], 'corr_y': []}

    for sub in sub_list:

        try:

            mean_fd = params.loc[sub, 'mean_fd']
            dvars = params.loc[sub, 'dvars']
            corr_x = pd.DataFrame.from_csv(resample_path + sub + '//gsr0_train1_model_parameters.csv')['corr_x'][0]
            corr_y = pd.DataFrame.from_csv(resample_path + sub + '//gsr0_train1_model_parameters.csv')['corr_y'][0]

            motion_dict['mean_fd'].append(mean_fd)
            motion_dict['dvars'].append(dvars)
            motion_dict['corr_x'].append(corr_x)
            motion_dict['corr_y'].append(corr_y)

        except:

            continue

    val_range = np.linspace(np.nanmin(motion_dict[motion_type]), np.nanmax(motion_dict[motion_type]))
    z = np.polyfit(motion_dict[motion_type], motion_dict['corr_x'], 1)
    p = np.poly1d(z)
    r2_text = 'r2 value: ' + str(r2_score(motion_dict[motion_type], p(motion_dict['corr_x'])))

    plt.figure()
    plt.title('Linear Fit for ' + motion_type + ' in x')
    plt.xlabel(motion_type)
    plt.ylabel('Correlation Values')
    plt.scatter(motion_dict[motion_type], motion_dict['corr_x'], label='Correlation values')
    plt.plot(val_range, p(val_range), color='r', label=r2_text)
    plt.legend()
    plt.show()

    val_range = np.linspace(np.nanmin(motion_dict[motion_type]), np.nanmax(motion_dict[motion_type]))
    z = np.polyfit(motion_dict[motion_type], motion_dict['corr_y'], 1)
    p = np.poly1d(z)
    r2_text = 'r2 value: ' + str(r2_score(motion_dict[motion_type], p(motion_dict['corr_y'])))

    plt.figure()
    plt.title('Linear Fit for ' + motion_type + ' in y')
    plt.xlabel(motion_type)
    plt.ylabel('Correlation Values')
    plt.scatter(motion_dict[motion_type], motion_dict['corr_y'], label='Correlation values')
    plt.plot(val_range, p(val_range), color='r', label=r2_text)
    plt.legend()
    plt.show()


def scale_x_pos(fixation):

    """Scales fixation series from ET to match monitor dimensions of PEER in the x-direction

    :param fixation: Fixation point
    :return: Scaled fixation point
    """

    return (fixation - 400) * (1680 / 800)


def scale_y_pos(fixation):

    """Scales fixation series from ET to match monitor dimensions of PEER in the y-direction

    :param fixation: Fixation point
    :return: Scaled fixation point
    """

    return -((fixation - 300) * (1050 / 600))


def et_samples_to_pandas(sub):

    """Converts raw text output from eye-tracker to pandas dataframe

    :param sub: Subject ID
    :return: Dataframe with eye-tracking raw samples
    """

    sub = sub.strip('sub-')

    with open(eye_tracking_path + sub + '/Eyetracking/txt/' + sub + '_Video4_Samples.txt') as f:
        reader = csv.reader(f, delimiter='\t')
        content = list(reader)[38:]

        headers = content[0]

        df = pd.DataFrame(content[1:], columns=headers, dtype='float')

    msg_time = list(df[df.Type == 'MSG'].Time)

    start_time = float(msg_time[2])

    df_msg_removed = df[(df.Time > start_time)][['Time',
                                                 'R POR X [px]',
                                                 'R POR Y [px]']]

    df_msg_removed.update(df_msg_removed['R POR X [px]'].apply(scale_x_pos))
    df_msg_removed.update(df_msg_removed['R POR Y [px]'].apply(scale_y_pos))

    return df_msg_removed, start_time


def average_fixations_per_tr(df, start_time):

    """Averages fixation series over each TR block

    :param df: Dataframe containing raw data from eye-tracker
    :param start_time: Time when eye-tracking data for The Present begins
    :return: Dataframe containing averaged fixation series for each TR block
    """

    mean_fixations = []

    movie_volume_count = 250
    movie_TR = 800  # in milliseconds

    for num in range(movie_volume_count):

        bin0 = start_time + num * 1000 * movie_TR
        bin1 = start_time + (num + 1) * 1000 * movie_TR
        df_temp = df[(df.Time >= bin0) & (df.Time <= bin1)]

        x_pos = np.mean(df_temp['R POR X [px]'])
        y_pos = np.mean(df_temp['R POR Y [px]'])

        mean_fixations.append([x_pos, y_pos])

    df = pd.DataFrame(mean_fixations, columns=(['x_pred', 'y_pred']))

    return df


def save_mean_fixations(mean_df):

    """Saves averaged eye-tracker predictions to csv

    :param mean_df: Dataframe containing averaged fixation series for each TR block
    :return: Saves predictions to csv
    """

    mean_df.to_csv(hbm_path + sub + '/et_device_pred.csv')


def create_eye_tracker_fixation_series(sub):

    """Creates and saves eye tracker fixation series from raw eye-tracker data

    :param sub: Subject ID
    :return: CSV containing averaged fixation series from raw eye-tracking data
    """

    try:

        if os.path.exists('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/et_device_pred.csv'):

            print('ET fixation series already saved for ' + sub)

        else:

            df_output, start_time = et_samples_to_pandas(sub)
            mean_df = average_fixations_per_tr(df_output, start_time)
            save_mean_fixations(mean_df)
            print('Completed processing ' + sub)

    except:

        print('Error processing ' + sub)


def create_sub_list_with_et_and_peer(full_list):

    """Creates a list of subjects with both ET and PEER predictions

    :param full_list: List of subject IDs containing all subjects with at least 2/3 valid calibration scans
    :return: Subject list with both ET and PEER predictions
    """

    et_list = []

    for sub in full_list:

        if (os.path.exists('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/et_device_pred.csv')) and \
                (os.path.exists('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/gsr0_train1_model_tp_predictions.csv')):

            et_list.append(sub)

    return et_list


def compare_et_and_peer(sub, plot=False):

    et_df = pd.DataFrame.from_csv('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/et_device_pred.csv')

    peer_df = pd.DataFrame.from_csv('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/no_gsr_train1_tp_pred.csv')

    corr_val_x = pearsonr(et_df['x_pred'], peer_df['x_pred'])[0]
    corr_val_y = pearsonr(et_df['y_pred'], peer_df['y_pred'])[0]

    if plot:

        plt.figure(figsize=(10,5))
        plt.plot(np.linspace(0, 249, 250), et_df['x_pred'], 'r-', label='eye-tracker')
        plt.plot(np.linspace(0, 249, 250), peer_df['x_pred'], 'b-', label='PEER')
        plt.title(sub + ' with correlation value: ' + str(corr_val_x)[:5])
        plt.xlabel('TR')
        plt.ylabel('Fixation location (px)')
        plt.legend()
        plt.show()

        plt.figure(figsize=(10,5))
        plt.plot(np.linspace(0, 249, 250), et_df['y_pred'], 'r-', label='eye-tracker')
        plt.plot(np.linspace(0, 249, 250), peer_df['y_pred'], 'b-', label='PEER')
        plt.title(sub + ' with correlation value: ' + str(corr_val_y)[:5])
        plt.xlabel('TR')
        plt.ylabel('Fixation location (px)')
        plt.legend()
        plt.show()

    return corr_val_x, corr_val_y


def create_swarm_plot_for_et_and_peer(sub_list):

    corr_et_peer_x = []
    corr_et_peer_y = []

    for sub in sub_list:

        try:

            corr_val_x, corr_val_y = compare_et_and_peer(sub, plot=False)
            corr_et_peer_x.append(corr_val_x)
            corr_et_peer_y.append(corr_val_y)

        except:

            print('Subject has TP PEER predictions missing')

    index_vals = ['Peer vs. ET' for x in range(len(corr_et_peer_x))]

    swarm_dict = {'index': index_vals, 'corr_x': corr_et_peer_x, 'corr_y': corr_et_peer_y}

    swarm_df = pd.DataFrame.from_dict(swarm_dict)

    sns.set()
    ax = sns.swarmplot(x='index', y='corr_x', data=swarm_df)
    ax.set(title='Distribution of Correlation Values for ET vs. PEER Fixation Series in x')
    plt.show()

    sns.set()
    ax = sns.swarmplot(x='index', y='corr_y', data=swarm_df)
    ax.set(title='Distribution of Correlation Values for ET vs. PEER Fixation Series in y')
    plt.show()

    return corr_et_peer_x, corr_et_peer_y


def create_corr_matrix(sub_list):
    corr_matrix_tp_x = []
    corr_matrix_dm_x = []
    corr_matrix_tp_y = []
    corr_matrix_dm_y = []
    count = 0

    for sub in sub_list:

        try:

            if count == 0:
                '/data2/Projects/Jake/Human_Brain_Mapping/sub-5002891/gsr0_train1_model_dm_predictions.csv'

                expected_value = len(pd.read_csv(resample_path + sub + '/tppredictions.csv')['x_pred'])
                count += 1

            tp_x = np.array(pd.read_csv(resample_path + sub + '/gsr0_train1_model_tp_predictions.csv')['x_pred'])
            tp_y = np.array(pd.read_csv(resample_path + sub + '/gsr0_train1_model_tp_predictions.csv')['y_pred'])
            dm_x = np.array(pd.read_csv(resample_path + sub + '/gsr0_train1_model_dm_predictions.csv')['x_pred'][:250])
            dm_y = np.array(pd.read_csv(resample_path + sub + '/gsr0_train1_model_dm_predictions.csv')['y_pred'][:250])

            if (len(tp_x) == expected_value) & (len(dm_x) == expected_value):
                corr_matrix_tp_x.append(tp_x)
                corr_matrix_dm_x.append(tp_y)
                corr_matrix_tp_y.append(dm_x)
                corr_matrix_dm_y.append(dm_y)

        except:

            continue

    x_matrix = np.concatenate([corr_matrix_tp_x, corr_matrix_dm_x])
    y_matrix = np.concatenate([corr_matrix_tp_y, corr_matrix_dm_y])

    corr_matrix_x = np.corrcoef(x_matrix)
    corr_matrix_y = np.corrcoef(y_matrix)

    return corr_matrix_x, corr_matrix_y, corr_matrix_tp_x, corr_matrix_tp_y, corr_matrix_dm_x, corr_matrix_dm_y


def plot_correlation_matrix(correlation_matrix, dir_='x'):
    pcolor(correlation_matrix)
    plt.title('Correlation Matrix for TP and DM in ' + dir_)
    colorbar()
    show()


def separate_grouping(in_mat):

    fv = int(len(in_mat[0]))
    sv = fv / 2

    wi_ss = []
    wo_ss = []

    for numx in range(fv):
        for numy in range(fv):

            if (numx > sv) and (numy > sv) and (numx != numy):

                wi_ss.append(in_mat[numx][numy])

            elif (numx < sv) and (numy < sv) and (numx != numy):

                wi_ss.append(in_mat[numx][numy])

            else:

                if numx != numy:

                    wo_ss.append(in_mat[numx][numy])

    return wi_ss, wo_ss


def create_df_containing_within_without_separation(matrix_x, matrix_y):

    wi_ss_x, wo_ss_x = separate_grouping(matrix_x)
    wi_ss_y, wo_ss_y = separate_grouping(matrix_y)

    wi_label = ['Within' for x in range(len(wi_ss_x))]
    wo_label = ['Between' for x in range(len(wo_ss_x))]

    df_dict = {'x': np.concatenate([wi_ss_x, wo_ss_x]), 'y': np.concatenate([wi_ss_y, wo_ss_y]),
               '': np.concatenate([wi_label, wo_label]),
               'x_ax': ['Naturalistic Viewing' for x in range(len(wi_ss_x) + len(wo_ss_x))]}

    df = pd.DataFrame.from_dict(df_dict)

    return df, wi_ss_x, wo_ss_x, wi_ss_y, wo_ss_y

# within_without_df, wi_ss_x, wo_ss_x, wi_ss_y, wo_ss_y = create_df_containing_within_without_separation(corr_matrix_x, corr_matrix_y)

def plot_within_without_groups(df, dir_='x'):

    sns.set()
    plt.title('Within and Between Movie Correlation Discriminability in ' + dir_)
    sns.violinplot(x='x_ax', y=dir_, hue='', data=df, split=True,
                   inner='quart', palette={'Within': 'b', 'Between': 'y'})
    plt.show()

# plot_within_without_groups(within_without_df, dir_='x')

def grouping_ss(within, without):

    wi_mean = np.nanmean(within)
    wo_mean = np.nanmean(without)
    wi_stdv = np.nanstd(within)
    wo_stdv = np.nanstd(without)

    return wi_mean, wo_mean, wi_stdv, wo_stdv

# wi_mean_x, wo_mean_x, wi_stdv_x, wo_stdv_x = grouping_ss(wi_ss_x, wo_ss_x)
# wi_mean_y, wo_mean_y, wi_stdv_y, wo_stdv_y = grouping_ss(wi_ss_y, wo_ss_y)

def bin_class(sub_list, tt_split=.5):

    # Create all dm and tp vectors with targets
    # Divide into training and testing sets

    corr_matrix_x, corr_matrix_y, tp_x, tp_y, dm_x, dm_y = create_corr_matrix(sub_list)

    svm_dict = {}

    for item in range(len(tp_x[0])):

        svm_dict[item] = []

    for fix in range(len(tp_x[0])):

        temp_list = []

        for item in range(len(tp_x)):

            temp_list.append(tp_x[item][fix])

        svm_dict[fix] = temp_list

    for fix in range(len(dm_x[0])):

        temp_list = []

        for item in range(len(dm_x)):

            temp_list.append(dm_x[item][fix])

        svm_dict[fix] = svm_dict[fix] + temp_list

    tp_labels = [0 for x in range(len(tp_x))]
    dm_labels = [1 for x in range(len(dm_x))]
    label_list = tp_labels + dm_labels

    svm_dict['labels'] = label_list

    df_x = pd.DataFrame.from_dict(svm_dict)

    svm_dict = {}

    for item in range(len(tp_y[0])):

        svm_dict[item] = []

    for fix in range(len(tp_y[0])):

        temp_list = []

        for item in range(len(tp_y)):

            temp_list.append(tp_y[item][fix])

        svm_dict[fix] = temp_list

    for fix in range(len(dm_y[0])):

        temp_list = []

        for item in range(len(dm_y)):

            temp_list.append(dm_y[item][fix])

        svm_dict[fix] = svm_dict[fix] + temp_list

    tp_labels = [0 for x in range(len(tp_y))]
    dm_labels = [1 for x in range(len(dm_y))]
    label_list = tp_labels + dm_labels

    svm_dict['labels'] = label_list

    df_y = pd.DataFrame.from_dict(svm_dict)

    train_set_x, test_set_x = train_test_split(df_x, test_size=tt_split)

    train_data_x = train_set_x.drop(['labels'], axis=1)
    test_data_x = test_set_x.drop(['labels'], axis=1)
    train_targets_x = train_set_x[['labels']]
    test_targets_x = test_set_x[['labels']]

    train_set_y, test_set_y = train_test_split(df_y, test_size=tt_split)

    train_data_y = train_set_y.drop(['labels'], axis=1)
    test_data_y = test_set_y.drop(['labels'], axis=1)
    train_targets_y = train_set_y[['labels']]
    test_targets_y = test_set_y[['labels']]

    clfx = svm.SVC(C=100, tol=.0001, kernel='linear', verbose=1, probability=True)
    clfy = svm.SVC(C=100, tol=.0001, kernel='linear', verbose=1, probability=True)

    clfx.fit(train_data_x, train_targets_x)
    predictions_x = clfx.predict(test_data_x)
    clfy.fit(train_data_y, train_targets_y)
    predictions_y = clfy.predict(test_data_y)\

    print('Confusion Matrix in x')
    print(confusion_matrix(predictions_x, test_targets_x))
    print('Confusion Matrix in y')
    print(confusion_matrix(predictions_y, test_targets_y))

    probas_x = clfx.predict_proba(test_data_x)
    probas_y = clfy.predict_proba(test_data_y)

    fpr_x, tpr_x, thresholds = roc_curve(test_targets_x, probas_x[:, 1])
    roc_auc_x = auc(fpr_x, tpr_x)

    fpr_y, tpr_y, thresholds = roc_curve(test_targets_y, probas_y[:, 1])
    roc_auc_y = auc(fpr_y, tpr_y)

    plt.figure()
    plt.plot(fpr_x, tpr_x, label='AUROC = ' + str(roc_auc_x)[:6])
    plt.plot([0, 1], [0, 1], color='k', linestyle='--')
    plt.title('ROC Curve for SVM in x')
    plt.xlabel('FPR')
    plt.ylabel('TPR')
    plt.legend()
    plt.show()

    plt.figure()
    plt.plot(fpr_y, tpr_y, label='AUROC = ' + str(roc_auc_y)[:6])
    plt.plot([0, 1], [0, 1], color='k', linestyle='--')
    plt.title('ROC Curve for SVM in y')
    plt.xlabel('FPR')
    plt.ylabel('TPR')
    plt.legend()
    plt.show()




# For every volume, get the diversity score for ET and PEER
# 1)x create uniform histogram with 30x30 bins, with 35 vertical and 56 horizontal
# 2)o create histogram with fixations for each volume
# 3)o calculate absolute deviation between uniform and fixation
# 4)o compare diversity scores from ET and PEER

def diversity_score_analysis():

monitor_width = 1680
monitor_height = 1050

uniform_val = float(1 / ((monitor_width / 30) * (monitor_height / 30)))

params, sub_list = load_data(min_scan=2)

x_hm, y_hm, x_hm_without_end, y_hm_without_end = stack_fixation_series(params, viewtype='tp', sorted_by='mean_fd')





fixation_bins_vols = {}

for vol in range(len(x_hm_without_end[0])):

    fixation_bins_vols[str(vol)] = []

for vol in range(len(x_hm_without_end[0])):

    fixation_bins = {}

    for bin1 in range(int(monitor_width / 30)):

        fix_dict = {}

        for bin2 in range(int(monitor_height / 30)):

            fix_dict[str(bin2)] = []

        fixation_bins[str(bin1)] = fix_dict

    fixation_bins_vols[str(vol)] = fixation_bins






fixation_series = {}

for vol in range(len(x_hm_without_end[0])):

    fixation_series[vol] = []

for vol in range(len(x_hm_without_end[0])):

    for sub in range(len(x_hm_without_end)):

        fixation_series[vol].append([x_hm_without_end[sub][vol], y_hm_without_end[sub][vol]])

out_of_bounds = {}
sum_stats_per_vol = {}

for vol in range(len(x_hm_without_end[0])):

    out_of_bounds_count = 0
    out_of_bounds[vol] = []

    total_count = 0
    present_in_vol = 0

    for sub in range(len(x_hm_without_end)):

        x_bin = str(int(np.floor((x_hm_without_end[sub][vol] + 840)/30)))
        y_bin = str(int(np.floor((y_hm_without_end[sub][vol] + 525)/30)))

        if (int(x_bin) < 0) or (int(x_bin) > 55) or (int(y_bin) < 0) or (int(y_bin) > 34):

            out_of_bounds_count += 1
            total_count += 1

        else:

            fixation_bins_vols[str(vol)][x_bin][y_bin].append('fixation')
            total_count += 1
            present_in_vol += 1

    out_of_bounds[vol] = out_of_bounds_count
    expected_count = present_in_vol + out_of_bounds_count

    sum_stats_per_vol[str(vol)] = {'total count': total_count, 'expected count': expected_count,
                                   'out of bounds count': out_of_bounds_count, 'fixation count': present_in_vol}


for vol in range(len(x_hm_without_end[0])):

    for bin1 in fixation_bins.keys():

        for bin2 in fixation_bins['0'].keys():

            fixation_bins_vols[str(vol)][bin1][bin2] = abs(float(len(fixation_bins[bin1][bin2]) /\
                                                                 (sum_stats_per_vol[str(vol)]['fixation count'])) - \
                                                           uniform_val)

diversity_score_dict = {}

for vol in range(len(x_hm_without_end[0])):

    count_val = 0

    for bin1 in fixation_bins_vols[str(vol)].keys():

        for bin2 in fixation_bins_vols[str(vol)]['0'].keys():

            count_val += fixation_bins_vols[str(vol)][bin1][bin2]

    diversity_score_dict[str(vol)] = count_val - abs((uniform_val - 1/sum_stats_per_vol[str(vol)]['fixation count']))*397

div_scores_list = list(diversity_score_dict.values())

plt.figure()
plt.plot(np.linspace(0, len(div_scores_list)-5, len(div_scores_list)-5), div_scores_list[5:])
plt.show()






########################################################################################################################




def extract_corr_values():

    params = pd.read_csv('model_outputs.csv', index_col='subject', dtype=object)
    params = params.convert_objects(convert_numeric=True)
    params = params[params.scan_count == 3]
    sub_list = params.index.values.tolist()
    resample_path = '/data2/Projects/Jake/Human_Brain_Mapping/'

    x_dict = {'no_gsr_train1': [], 'no_gsr_train3': [], 'no_gsr_train13': [], 'gsr_train1': []}
    y_dict = {'no_gsr_train1': [], 'no_gsr_train3': [], 'no_gsr_train13': [], 'gsr_train1': []}

    for sub in sub_list:

        try:

            x1 = pd.read_csv(resample_path + sub + '/parameters_no_gsr_train1.csv')['corr_x'][0]
            x2 = pd.read_csv(resample_path + sub + '/parameters_no_gsr_train3.csv')['corr_x'][0]
            x3 = pd.read_csv(resample_path + sub + '/parameters_no_gsr_train13.csv')['corr_x'][0]
            x4 = pd.read_csv(resample_path + sub + '/parameters_gsr_two_scans.csv')['corr_x'][0]

            x_dict['no_gsr_train1'].append(x1)
            x_dict['no_gsr_train3'].append(x2)
            x_dict['no_gsr_train13'].append(x3)
            x_dict['gsr_train1'].append(x4)

            y1 = pd.read_csv(resample_path + sub + '/parameters_no_gsr_train1.csv')['corr_y'][0]
            y2 = pd.read_csv(resample_path + sub + '/parameters_no_gsr_train3.csv')['corr_y'][0]
            y3 = pd.read_csv(resample_path + sub + '/parameters_no_gsr_train13.csv')['corr_y'][0]
            y4 = pd.read_csv(resample_path + sub + '/parameters_gsr_two_scans.csv')['corr_y'][0]

            y_dict['no_gsr_train1'].append(y1)
            y_dict['no_gsr_train3'].append(y2)
            y_dict['no_gsr_train13'].append(y3)
            y_dict['gsr_train1'].append(y4)

        except:

            print(sub + ' not successful')

    return x_dict, y_dict


def threshold_proportion(threshold=.50, type='gsr'):

    x_fract = len([x for x in x_dict[type] if x > threshold]) / len(x_dict[type])
    y_fract = len([x for x in y_dict[type] if x > threshold]) / len(y_dict[type])

    print(x_fract, y_fract)


# #############################################################################
# SVM for binary classification

# #############################################################################
# Generalizable classifier


# #############################################################################
# Misc

def general_classifier(reg_list):

    funcTime = datetime.now()

    train_vectors1 = []
    train_vectors2 = []
    test_vectors = []

    for sub in reg_list[:train_set_count]:

        print('starting participant ' + str(sub))

        scan1 = nib.load(resample_path + sub + '/peer1_eyes.nii.gz')
        scan1 = scan1.get_data()
        scan2 = nib.load(resample_path + sub + '/peer2_eyes.nii.gz')
        scan2 = scan2.get_data()
        scan3 = nib.load(resample_path + sub + '/peer3_eyes.nii.gz')
        scan3 = scan3.get_data()

        for item in [scan1, scan2, scan3]:

            for vol in range(item.shape[3]):

                output = np.multiply(eye_mask, item[:, :, :, vol])

                item[:, :, :, vol] = output

        for item in [scan1, scan2, scan3]:

            print('Initial average: ' + str(np.average(item)))
            item = mean_center_var_norm(item)
            print('Mean centered average: ' + str(np.average(item)))
            item = gs_regress(item, 0, item.shape[0]-1, 0, item.shape[1]-1, 0, item.shape[2]-1)
            print('GSR average: ' + str(np.average(item)))

        listed1 = []
        listed2 = []
        listed_testing = []

        print('beginning vectors')

        for tr in range(int(scan1.shape[3])):

            tr_data1 = scan1[:,:,:, tr]
            vectorized1 = np.array(tr_data1.ravel())
            listed1.append(vectorized1)

            tr_data2 = scan3[:,:,:, tr]
            vectorized2 = np.array(tr_data2.ravel())
            listed2.append(vectorized2)

            te_data = scan2[:,:,:, tr]
            vectorized_testing = np.array(te_data.ravel())
            listed_testing.append(vectorized_testing)

        train_vectors1.append(listed1)
        test_vectors.append(listed_testing)
        train_vectors2.append(listed2)

    full_train1 = []
    full_test = []
    full_train2 = []

    for part in range(len(reg_list[:train_set_count])):
        for vect in range(scan1.shape[3]):
            full_train1.append(train_vectors1[part][vect])
            full_test.append(test_vectors[part][vect])
            full_train2.append(train_vectors2[part][vect])

        # train_vectors1 = np.asarray(listed1)
        # test_vectors = np.asarray(listed_testing)
        # train_vectors2 = np.asarray(listed2)

        # #############################################################################
        # Averaging training signal

    print('average vectors')

    train_vectors = data_processing(3, full_train1, full_train2)

        # #############################################################################
        # Import coordinates for fixations

    print('importing fixations')

    fixations = pd.read_csv('stim_vals.csv')
    x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), len(reg_list[:train_set_count])) * monitor_width / 2, 3 - 1)
    y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), len(reg_list[:train_set_count])) * monitor_height / 2, 3 - 1)

        # #############################################################################
        # Create SVR Model

    x_model, y_model = create_model(train_vectors, x_targets, y_targets)
    print('Training completed: ' + str(datetime.now() - funcTime))

    for gen in range(len(reg_list)):

        gen = gen+1
        predicted_x = x_model.predict(full_test[scan1.shape[3]*(gen-1):scan1.shape[3]*(gen)])
        predicted_y = y_model.predict(full_test[scan1.shape[3]*(gen-1):scan1.shape[3]*(gen)])
        axis_plot(fixations, predicted_x, predicted_y, sub, train_sets=1)



        x_res = []
        y_res = []

        sub = reg_list[gen-1]

        for num in range(27):

            nums = num * 5

            for values in range(5):
                error_x = (abs(x_targets[num] - predicted_x[nums + values])) ** 2
                error_y = (abs(y_targets[num] - predicted_y[nums + values])) ** 2
                x_res.append(error_x)
                y_res.append(error_y)

        x_error = np.sqrt(np.sum(np.array(x_res)) / 135)
        y_error = np.sqrt(np.sum(np.array(y_res)) / 135)
        print([x_error, y_error])

        params.loc[sub, 'x_error_within'] = x_error
        params.loc[sub, 'y_error_within'] = y_error
        params.to_csv('subj_params.csv')
        print('participant ' + str(sub) + ' complete')


# #############################################################################
# Turning each set of weights into a Nifti image for coefficient of variation map analysis

# reg_list = ['sub-5986705','sub-5375858','sub-5292617','sub-5397290','sub-5844932','sub-5787700','sub-5797959',
#             'sub-5378545','sub-5085726','sub-5984037','sub-5076391','sub-5263388','sub-5171285',
#             'sub-5917648','sub-5814325','sub-5169146','sub-5484500','sub-5481682','sub-5232535','sub-5905922',
#             'sub-5975698','sub-5986705','sub-5343770']
#
# train_set_count = len(reg_list) - 1
# resample_path = '/data2/Projects/Jake/Resampled/'
# eye_mask = nib.load('/data2/Projects/Jake/Resampled/eye_all_sub.nii.gz')
# eye_mask = eye_mask.get_data()
# for sub in reg_list:
#
#     train_vectors1 = []
#     train_vectors2 = []
#     test_vectors = []
#
#     print('starting participant ' + str(sub))
#
#     scan1 = nib.load(resample_path + sub + '/peer1_eyes.nii.gz')
#     scan1 = scan1.get_data()
#     scan2 = nib.load(resample_path + sub + '/peer2_eyes.nii.gz')
#     scan2 = scan2.get_data()
#     scan3 = nib.load(resample_path + sub + '/peer3_eyes.nii.gz')
#     scan3 = scan3.get_data()
#
#     for item in [scan1, scan2, scan3]:
#
#         for vol in range(item.shape[3]):
#             output = np.multiply(eye_mask, item[:, :, :, vol])
#
#             item[:, :, :, vol] = output
#
#     for item in [scan1, scan2, scan3]:
#         print('Initial average: ' + str(np.average(item)))
#         item = mean_center_var_norm(item)
#         print('Mean centered average: ' + str(np.average(item)))
#         item = gs_regress(item, 0, item.shape[0] - 1, 0, item.shape[1] - 1, 0, item.shape[2] - 1)
#         print('GSR average: ' + str(np.average(item)))
#
#     listed1 = []
#     listed2 = []
#     listed_testing = []
#
#     print('beginning vectors')
#
#     for tr in range(int(scan1.shape[3])):
#         tr_data1 = scan1[:, :, :, tr]
#         vectorized1 = np.array(tr_data1.ravel())
#         listed1.append(vectorized1)
#
#         tr_data2 = scan3[:, :, :, tr]
#         vectorized2 = np.array(tr_data2.ravel())
#         listed2.append(vectorized2)
#
#         te_data = scan2[:, :, :, tr]
#         vectorized_testing = np.array(te_data.ravel())
#         listed_testing.append(vectorized_testing)
#
#     train_vectors1.append(listed1)
#     test_vectors.append(listed_testing)
#     train_vectors2.append(listed2)
#
#     full_train1 = []
#     full_test = []
#     full_train2 = []
#
#     for part in range(len(reg_list[:train_set_count])):
#         for vect in range(scan1.shape[3]):
#             full_train1.append(train_vectors1[part][vect])
#             full_test.append(test_vectors[part][vect])
#             full_train2.append(train_vectors2[part][vect])
#
#         # train_vectors1 = np.asarray(listed1)
#         # test_vectors = np.asarray(listed_testing)
#         # train_vectors2 = np.asarray(listed2)
#
#         # #############################################################################
#         # Averaging training signal
#
#     print('average vectors')
#
#     train_vectors = data_processing(3, full_train1, full_train2)
#
#     # #############################################################################
#     # Import coordinates for fixations
#
#     print('importing fixations')
#
#     fixations = pd.read_csv('stim_vals.csv')
#     x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), len(reg_list[:train_set_count])) * monitor_width / 2, 3 - 1)
#     y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), len(reg_list[:train_set_count])) * monitor_height / 2,
#                         3 - 1)
#
#     # #############################################################################
#     # Create SVR Model
#
#     x_model, y_model = create_model(train_vectors, x_targets, y_targets)
#
#     x_model_coef = x_model.coef_
#     y_model_coef = y_model.coef_
#
#     x_model_coef = np.array(x_model_coef).reshape((35, 17, 14))
#     y_model_coef = np.array(y_model_coef).reshape((35, 17, 14))
#
#     img = nib.Nifti1Image(x_model_coef, np.eye(4))
#     img.header['pixdim'] = np.array([-1, 3, 3, 3, .80500031, 0, 0, 0])
#     img.to_filename('/data2/Projects/Jake/weights_coef/' + str(sub) + 'x.nii.gz')
#     img = nib.Nifti1Image(y_model_coef, np.eye(4))
#     img.header['pixdim'] = np.array([-1, 3, 3, 3, .80500031, 0, 0, 0])
#     img.to_filename('/data2/Projects/Jake/weights_coef/' + str(sub) + 'y.nii.gz')



# #############################################################################
# Creating a coefficient of variation map

# total = nib.load('/data2/Projects/Jake/weights_coef/totalx.nii.gz')
# data = total.get_data()
#
# coef_array = np.zeros((data.shape[0], data.shape[1], data.shape[2]))
#
# for x in range(data.shape[0]):
#     for y in range(data.shape[1]):
#         for z in range(data.shape[2]):
#
#             vmean = np.mean(np.array(data[x, y, z, :]))
#             vstdev = np.std(np.array(data[x, y, z, :]))
#
#             for time in range(data.shape[3]):
#                 if np.round(vmean, 2) == 0.00:
#                     coef_array[x, y, z] = float(vstdev)
#                 else:
#                     coef_array[x, y, z] = float(vstdev)
#
# img = nib.Nifti1Image(coef_array, np.eye(4))
# img.header['pixdim'] = np.array([-1, 3, 3, 3, .80500031, 0, 0, 0])
# img.to_filename('/data2/Projects/Jake/weights_coef/x_coef_map_stdev.nii.gz')
#
# modified = nib.load('/data2/Projects/Jake/weights_coef/x_coef_map.nii.gz')
# data = modified.get_data()
#
# for x in range(data.shape[0]):
#     for y in range(data.shape[1]):
#         for z in range(data.shape[2]):
#             if abs(data[x, y, z]) > 100 or abs(data[x, y, z] < 3) and abs(np.round(data[x, y, z],2) != 0.00):
#                 data[x, y, z] = 1
#             else:
#                 data[x, y, z] = 0
#
# img = nib.Nifti1Image(data, np.eye(4))
# img.header['pixdim'] = np.array([-1, 3, 3, 3, .80500031, 0, 0, 0])
# img.to_filename('/data2/Projects/Jake/eye_masks/x_coef_map_eyes_100_5.nii.gz')

# #############################################################################
# Get distribution of voxel intensities from isolated eye coefficient of variation map to determine intensity threshold

# coef_sub = nib.load('/data2/Projects/Jake/weights_coef/x_coef_map.nii.gz')
# data = coef_sub.get_data()
#
# data_rav = data.ravel()
# data_rav = np.nan_to_num(data_rav)
# data_rav = np.array([x for x in data_rav if x != 0])
#
# xbins = np.histogram(data_rav, bins=300)[1]
#
# values, base = np.histogram(data_rav, bins=30)
# cumulative = np.cumsum(values)
#
# plt.figure()
# plt.hist(data_rav, xbins, color='b')
# plt.title('Full Raw')
# # plt.savefig('/home/json/Desktop/peer/eye_distr.png')
# plt.show()
# # plt.plot(base[:-1], cumulative/len(data_rav), color='g')
# # plt.show()

# #############################################################################
# Determine percentiles

# values, base = np.histogram(data_rav, bins=len(data_rav))
# cumulative = np.cumsum(values)/len(data_rav)
#
# for num in range(len(data_rav)):
#     if np.round(cumulative[num], 3) == .05:
#         print(base[num])
#
# # value_of_interest = base[percentile]

# #############################################################################
# Visualize error vs motion

# params = pd.read_csv('peer_didactics.csv', index_col='subject')
# params = params[params['x_gsr'] < 50000][params['y_gsr'] < 50000][params['mean_fd'] < 3.8][params['dvars'] < 1.5]
#
# # Need to fix script to not rely on indexing and instead include a subset based on mean and stdv parameters
# num_part = len(params)
#
# x_error_list = params.loc[:, 'x_gsr'][:num_part].tolist()
# y_error_list = params.loc[:, 'y_gsr'][:num_part].tolist()
# mean_fd_list = params.loc[:, 'mean_fd'][:num_part].tolist()
# dvars_list = params.loc[:, 'dvars'][:num_part].tolist()
#
# x_error_list = np.array([float(x) for x in x_error_list])
# y_error_list = np.array([float(x) for x in y_error_list])
# mean_fd_list = np.array([float(x) for x in mean_fd_list])
# dvars_list = np.array([float(x) for x in dvars_list])
#
# m1, b1 = np.polyfit(mean_fd_list, x_error_list, 1)
# m2, b2 = np.polyfit(mean_fd_list, y_error_list, 1)
# m3, b3 = np.polyfit(dvars_list, x_error_list, 1)
# m4, b4 = np.polyfit(dvars_list, y_error_list, 1)
#
# plt.figure(figsize=(8, 8))
# plt.subplot(2, 2, 1)
# plt.title('mean_fd vs. x_RMS')
# plt.scatter(mean_fd_list, x_error_list, s=5)
# plt.plot(mean_fd_list, m1*mean_fd_list + b1, '-', color='r')
# plt.subplot(2, 2, 2)
# plt.title('mean_fd vs. y_RMS')
# plt.scatter(mean_fd_list, y_error_list, s=5)
# plt.plot(mean_fd_list, m2*mean_fd_list + b2, '-', color='r')
# plt.subplot(2, 2, 3)
# plt.title('dvars vs. x_RMS')
# plt.scatter(dvars_list, x_error_list, s=5)
# plt.plot(dvars_list, m3*dvars_list + b3, '-', color='r')
# plt.subplot(2, 2, 4)
# plt.title('dvars vs. y_RMS')
# plt.scatter(dvars_list, y_error_list, s=5)
# plt.plot(dvars_list, m4*dvars_list + b4, '-', color='r')
# plt.show()

# fixations = pd.read_csv('stim_vals.csv')
# x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 1) * monitor_width / 2, 1)
# y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 1) * monitor_height / 2, 1)
#
# plt.figure()
# plt.scatter(x_targets, y_targets)
# plt.title('Calibration Screen')
# plt.savefig('/home/json/Desktop/peer/hbm_figures/calibration_screen.png', dpi=600)
# plt.show()

from scipy.stats import norm
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt

params = pd.read_csv('model_outputs.csv', index_col='subject', dtype=object)
params = params.convert_objects(convert_numeric=True)
sub_list = params.index.values.tolist()

data_path = '/data2/Projects/Lei/Peers/Prediction_data/'

dm_dist = []
tp_dist = []

prop_dm = []
prop_tp = []

for sub in sub_list:

    try:

        with open(data_path + sub + '/DM_eyemove.txt') as f:
            content = f.readlines()
        dm = [float(x.strip('\n')) for x in content if float(x.strip('\n')) < 2000]
        with open(data_path + sub + '/TP_eyemove.txt') as f:
            content = f.readlines()
        tp = [float(x.strip('\n')) for x in content if float(x.strip('\n')) < 2000]

        n_bins = 10
        threshold = 300

        prop_dm.append(len([x for x in dm if x < threshold]) / len(dm))
        prop_tp.append(len([x for x in tp if x < threshold]) / len(tp))

        mu, sigma = norm.fit(dm)
        n, bins_dm = np.histogram(dm, n_bins, normed=True)
        y_dm = mlab.normpdf(np.linspace(0, 300, 100), mu, sigma)

        mu, sigma = norm.fit(tp)
        n, bins_tp = np.histogram(tp, n_bins, normed=True)
        y_tp = mlab.normpdf(np.linspace(0, 300, 100), mu, sigma)

        if y_dm[0] < .01:

            dm_dist.append([np.linspace(0, 300, 100), y_dm])

        if y_tp[0] < .01:

            tp_dist.append([np.linspace(0, 300, 100), y_tp])

    except:

        continue

print(np.mean(prop_dm), np.mean(prop_tp))

figure_title = 'DM Eye Movement Magnitude Distributions'
plt.figure()
plt.title(figure_title)

for bins_, y_ in dm_dist:
    plt.plot(np.linspace(0, 300, 100), y_, linewidth=1, alpha=.5)
plt.xlim([0, 300])
# plt.savefig('/home/json/Desktop/' + figure_title + '.png', dpi=600)
plt.xlabel('Distance between 2-D fixation predictions')
plt.show()

above = []
mid = []
stdv = []
below = []

mean_ci_dm = [y for x,y in dm_dist]
mean_ci_tp = [y for x,y in tp_dist]

dm_mean = np.mean(mean_ci_dm, axis=0)
dm_below = dm_mean - 1.96 * np.std(mean_ci_dm, axis=0)
dm_above = dm_mean + 1.96 * np.std(mean_ci_dm, axis=0)

tp_mean = np.mean(mean_ci_dm, axis=0)
tp_below = tp_mean - 1.96 * np.std(mean_ci_tp, axis=0)
tp_above = tp_mean + 1.96 * np.std(mean_ci_tp, axis=0)

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import colorConverter as cc
import numpy as np


def plot_mean_and_CI(mean, lb, ub, color_mean=None, color_shading=None):
    # plot the shaded range of the confidence intervals

    figure_title = 'TP Eye Movement Magnitude Distributions'

    plt.fill_between(np.linspace(0, 300, 100), ub, lb,
                     color=color_shading, alpha=.5)
    # plot the mean on top
    # plt.plot(mean, color_mean)
    plt.plot(np.linspace(0, 300, 100), mean)
    plt.title(figure_title)
    plt.xlabel('Distance between 2-D fixation predictions')
    plt.savefig('/home/json/Desktop/peer/Figures/' + figure_title + '.png', dpi=600)


plot_mean_and_CI(tp_mean, tp_below, tp_above, color_mean='b', color_shading='b')


###### Squashing function

def squash(in_val, c1, c2):

    output = c1 + (c2 - c1) * np.tanh((in_val - c1)/(c2 - c1))

    return output

params = pd.read_csv('model_outputs.csv', index_col='subject', dtype=object)
params = params.convert_objects(convert_numeric=True)
sub_list = params.index.values.tolist()

for sub in sub_list:

    try:

        # with open(data_path + sub + '/DM_eyemove.txt') as f:
        #     content = f.readlines()
        # dm = [float(x.strip('\n')) for x in content if float(x.strip('\n')) ]
        with open(data_path + sub + '/TP_eyemove.txt') as f:
            content = f.readlines()
        tp = [float(x.strip('\n')) for x in content if float(x.strip('\n'))]

        # dm_mean = np.mean(dm)
        tp_mean = np.mean(tp)
        # dm_std = np.std(dm)
        tp_std = np.std(tp)

        # dm_z = [(x-dm_mean)/dm_std for x in dm]
        tp_z = [(x-tp_mean)/tp_std for x in tp]

        t_upper = 4.0
        t_lower = 2.5

        dm_squashed = []
        tp_squashed = []
        dm_spikes = []
        tp_spikes = []

        # for x in dm_z:
        #     if abs(x) < t_lower:
        #         dm_squashed.append(x)
        #         dm_spikes.append(0)
        #     else:
        #         dm_squashed.append(squash(x, t_lower, t_upper))
        #         dm_spikes.append(1)

        for x in tp_z:
            if abs(x) < t_lower:
                tp_squashed.append(x)
                tp_spikes.append(0)
            else:
                tp_squashed.append(squash(x, t_lower, t_upper))
                tp_spikes.append(1)

        # dm_output = [dm_mean + x*dm_std for x in dm_squashed]
        tp_output = [tp_mean + x*tp_std for x in tp_squashed]

        # with open('/data2/Projects/Lei/Peers/Prediction_data/' + sub + '/DM_eyemove_squashed.txt', 'w') as dm_file:
        #     for item in dm_output:
        #         dm_file.write("%s\n" % item)

        with open('/data2/Projects/Lei/Peers/Prediction_data/' + sub + '/TP_eyemove_squashed.txt', 'w') as tp_file:
            for item in tp_output:
                tp_file.write("%s\n" % item)

        # with open('/data2/Projects/Lei/Peers/Prediction_data/' + sub + '/DM_eyemove_spikes.txt', 'w') as dm_file:
        #     for item in dm_spikes:
        #         dm_file.write("%s\n" % item)

        with open('/data2/Projects/Lei/Peers/Prediction_data/' + sub + '/TP_eyemove_spikes.txt', 'w') as tp_file:
            for item in tp_spikes:
                tp_file.write("%s\n" % item)

    except:

        continue




#################################### Eye Tracking Analysis


# sample_list_with_both_et_and_peer = ['sub-5743805', 'sub-5783223']
# sub_list_with_et_and_peer
# subset_list = ['sub-5161062', 'sub-5127994', 'sub-5049983', 'sub-5036745', 'sub-5002891', 'sub-5041416']

corr_vals = []

for sub in sub_list_with_et_and_peer:
    try:
        temp_val = compare_et_and_peer(sub, plot=False)
        corr_vals.append([temp_val, sub])
        print(sub + ' processing completed.')
    except:
        continue

index_vals = np.zeros(len(corr_vals))
swarm_df = pd.DataFrame({'corr_x': corr_vals, 'index':index_vals})

plt.clf()
ax = sns.swarmplot(x='index', y='corr_x', data=swarm_df)
ax.set(title='Correlation Distribution for Eye-Tracker vs. PEER in x')
plt.show()






et_list = ['sub-5002891','sub-5016867','sub-5028550','sub-5032610','sub-5036745','sub-5041416',
 'sub-5049983',
 'sub-5127994',
 'sub-5161062',
 'sub-5162937',
 'sub-5169363',
 'sub-5190972',
 'sub-5206511',
 'sub-5219925',
 'sub-5227193',
 'sub-5231865',
 'sub-5238801',
 'sub-5249438',
 'sub-5266756',
 'sub-5284922',
 'sub-5291254',
 'sub-5291284',
 'sub-5310336',
 'sub-5319102',
 'sub-5342081',
 'sub-5375165',
 'sub-5378545',
 'sub-5396885',
 'sub-5397290',
 'sub-5422296',
 'sub-5422890',
 'sub-5465986',
 'sub-5472150',
 'sub-5476502',
 'sub-5484500',
 'sub-5505585',
 'sub-5506824',
 'sub-5531229',
 'sub-5534291',
 'sub-5536087',
 'sub-5552032',
 'sub-5565519',
 'sub-5569056',
 'sub-5574873',
 'sub-5593729',
 'sub-5601764',
 'sub-5617898',
 'sub-5630057',
 'sub-5631924',
 'sub-5642131',
 'sub-5652036',
 'sub-5659524',
 'sub-5669325',
 'sub-5673128',
 'sub-5730047',
 'sub-5730803',
 'sub-5743805',
 'sub-5755188',
 'sub-5755327',
 'sub-5773707',
 'sub-5783223',
 'sub-5794133',
 'sub-5797959',
 'sub-5808453',
 'sub-5814325',
 'sub-5814978',
 'sub-5820160',
 'sub-5824845',
 'sub-5837180',
 'sub-5844932',
 'sub-5852696',
 'sub-5858221',
 'sub-5865523',
 'sub-5865707',
 'sub-5920995',
 'sub-5931672',
 'sub-5942168',
 'sub-5982802',
 'sub-5984037',
 'sub-5986705']

def individual_series(peer_list, et_list):

    et_series = {}
    peer_series = {}

    for sub in peer_list:

        try:

            sub_df = pd.DataFrame.from_csv('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/no_gsr_train1_tp_pred.csv')
            sub_x = sub_df['x_pred']
            sub_y = sub_df['y_pred']

            peer_series[sub] = {'x': sub_x, 'y': sub_y}

        except:

            print('Error with subject ' + sub)

    for sub in et_list:

        try:

            sub_df = pd.DataFrame.from_csv('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/et_device_pred.csv')
            sub_x = sub_df['x_pred']
            sub_y = sub_df['y_pred']

            et_series[sub] = {'x': sub_x, 'y': sub_y}

        except:

            print('Error with subject ' + sub)

    return et_series, peer_series

def mean_series(peer_list, et_list):
    # peer_list = subjects with valid peer scans
    # et_list = subjects with valid et data

    et_series = {'x': [], 'y': []}
    peer_series = {'x': [], 'y': []}

    for sub in peer_list:

        try:

            sub_df = pd.DataFrame.from_csv('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/no_gsr_train1_tp_pred.csv')
            sub_x = sub_df['x_pred']
            sub_y = sub_df['y_pred']

            if len(sub_x) == 250:
                peer_series['x'].append(np.array(sub_x))
                peer_series['y'].append(np.array(sub_y))

            else:
                print(sub)

        except:

            print('Error with subject ' + sub)

    for sub in et_list:

        try:

            sub_df = pd.DataFrame.from_csv('/data2/Projects/Jake/Human_Brain_Mapping/' + sub + '/et_device_pred.csv')
            sub_x = sub_df['x_pred']
            sub_y = sub_df['y_pred']
            et_series['x'].append(np.array(sub_x))
            et_series['y'].append(np.array(sub_y))
        except:

            print('Error with subject ' + sub)

    et_mean_series = {'x': np.nanmean(et_series['x'], axis=0), 'y': np.nanmean(et_series['y'], axis=0)}
    peer_mean_series = {'x': np.nanmean(peer_series['x'], axis=0), 'y': np.nanmean(peer_series['y'], axis=0)}

    return et_mean_series, peer_mean_series

et_individual_series, peer_individual_series = individual_series(sub_list, et_list)
et_mean_series, peer_mean_series = mean_series(sub_list, et_list)

#### Create mean fixation series for PEER and ET gaze locations


sub_np5 = ['sub-5161062',
 'sub-5190972',
 'sub-5249438',
 'sub-5266756',
 'sub-5422296',
 'sub-5783223',
 'sub-5808453',
 'sub-5814978',
 'sub-5844932',
 'sub-5858221']


def compare_individual_and_mean_series(et_individual_series, et_mean_series, peer_individual_series, peer_mean_series, plot=False):

    sub_performance = {}

    for sub in et_list:

        try:

            corr_val_et_x = pearsonr(et_individual_series[sub]['x'], et_mean_series['x'])[0]
            corr_val_et_y = pearsonr(et_individual_series[sub]['y'], et_mean_series['y'])[0]
            corr_val_peer_x = pearsonr(peer_individual_series[sub]['x'], peer_mean_series['x'])[0]
            corr_val_peer_y = pearsonr(peer_individual_series[sub]['y'], peer_mean_series['y'])[0]

            sub_performance[sub] = {'et': {'x': corr_val_et_x, 'y': corr_val_et_y},
                                    'peer': {'x': corr_val_peer_x, 'y': corr_val_peer_y}}

        except:

            print('Error with subject ' + sub)

    return sub_performance

sub_performance = compare_individual_and_mean_series(et_individual_series, et_mean_series, peer_individual_series, peer_mean_series)

x_axis = np.linspace(0, len(et_individual_series[sub]['x']), len(et_individual_series[sub]['x']))

def plot_fixation_series_comparison(sub, dim='x', datatype='peer'):

    plt.figure(figsize=(10, 5))
    plt.plot(x_axis, peer_individual_series[sub][dim], 'r-', label='Individual')
    plt.plot(x_axis, peer_mean_series[dim], 'b-', label='Mean')
    plt.legend()
    plt.title(sub + ' for PEER with correlation value ' + str(sub_performance[sub][datatype][dim]))
    # plt.savefig('/home/json/Desktop/peer/et_peer_comparison/bad_et_mean/' + datatype + '_' + sub + '.png', dpi=600)
    plt.show()


for sub in list(sub_performance.keys())[:5]:

    plot_fixation_series_comparison(sub, dim='x', datatype='peer')






x_et = []
y_et = []
x_peer = []
y_peer = []

for sub in sub_performance.keys():
    x_et.append(sub_performance[sub]['et']['x'])
    y_et.append(sub_performance[sub]['et']['y'])
    x_peer.append(sub_performance[sub]['peer']['x'])
    y_peer.append(sub_performance[sub]['peer']['y'])


index_vals = np.zeros(len(sub_performance.keys()))
swarm_df = pd.DataFrame({'x_et': x_et, 'y_et': y_et, 'x_peer': x_peer, 'y_peer': y_peer, 'index': index_vals})





plt.clf()
ax = sns.swarmplot(x='index', y='y_peer', data=swarm_df)
ax.set(title='PEER for Individual vs. Mean in y')
plt.savefig('/home/json/Desktop/peer/et_peer_comparison/et_peer_mean_corr_swarm/PEER_y.png', dpi=600)
plt.show()







