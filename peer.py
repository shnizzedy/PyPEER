import os
import csv
import numpy as np
import pandas as pd
import nibabel as nib
from sklearn.svm import SVR
import matplotlib.pyplot as plt
from sklearn.model_selection import GridSearchCV


def gs_regress(data, xb, xe, yb, ye, zb, ze):

    global_mask = np.zeros([data.shape[0], data.shape[1], data.shape[2]])

    for x in range(int(global_mask.shape[0])):
        for y in range(int(global_mask.shape[1])):
            for z in range(int(global_mask.shape[2])):
                if x in range(xb, xe) and y in range(yb, ye) and z in range(zb, ze):

                    global_mask[x, y, z] = 1

    global_mask = np.array(global_mask, dtype=bool)

    regressor_map = {'constant': np.ones((data.shape[3], 1))}
    regressor_map['global'] = data[global_mask].mean(0)

    X = np.zeros((data.shape[3], 1))
    csv_filename = ''

    for rname, rval in regressor_map.items():
        X = np.hstack((X, rval.reshape(rval.shape[0], -1)))
        csv_filename += '_' + rname

    X = X[:, 1:]

    # csv_filename = csv_filename[1:]
    # csv_filename += '.csv'
    # csv_filename = os.path.join(os.getcwd(), csv_filename)
    # np.savetxt(csv_filename, X, delimiter='\t')

    Y = data[global_mask].T
    B = np.linalg.inv(X.T.dot(X)).dot(X.T).dot(Y)

    Y_res = Y - X.dot(B)

    data[global_mask] = Y_res.T

    return data

data_path = '/data2/Projects/Jake/RU/'
qap_path = '/data2/HBNcore/CMI_HBN_Data/MRI/RU/QAP/qap_functional_temporal.csv'
output_path = '/home/json/Desktop/peer/Figures'

monitor_width = 1680
monitor_height = 1050

# #############################################################################
# Update subject parameters sheet with new participants

params = pd.read_csv('subj_params.csv', index_col='subject', dtype=object)
sub_ref = params.index.values.tolist()

qap = pd.read_csv(qap_path, dtype=object)
qap['Participant'] = qap['Participant'].str.replace('_', '-')
# qap = qap.set_index('Participant')

x_b = 12; x_e = 40; y_b = 35; y_e = 50; z_b = 2; z_e = 13

subj_list = []

with open('subj_params.csv', 'a') as updated_params:
    writer = csv.writer(updated_params)

    for subject in os.listdir(data_path):
        if any(subject in x for x in sub_ref) and 'txt' not in subject:
            print(subject + ' is already in subj_params.csv')
        elif 'txt' not in subject:
            writer.writerow([subject, x_b, x_e, y_b, y_e, z_b, z_e])
            print('New participant ' + subject + ' was added')
            subj_list.append(subject)

# #############################################################################
# Import data

params = pd.read_csv('subj_params.csv', index_col='subject', dtype=object)

ru_set = params.index.values.tolist()[:350]

for set in ['sub-5773707']:

    xb = int(params.loc[set, 'x_start'])
    xe = int(params.loc[set, 'x_end'])
    yb = int(params.loc[set, 'y_start'])
    ye = int(params.loc[set, 'y_end'])
    zb = int(params.loc[set, 'z_start'])
    ze = int(params.loc[set, 'z_end'])

    try:

        print('Beginning analysis on participant ' + set)

        training1 = nib.load(data_path + set + '/PEER1_resampled.nii.gz')
        training1_data = training1.get_data()
        testing = nib.load(data_path + set + '/PEER2_resampled.nii.gz')
        testing_data = testing.get_data()

        try:

            training2 = nib.load(data_path + set + '/PEER3_resampled.nii.gz')
            training2_data = training2.get_data()
            scan_count = 3

        except:

            scan_count = 2

        # #############################################################################
        # Global Signal Regression

        if scan_count == 2:

            training1_data = gs_regress(training1_data, xb, xe, yb, ye, zb, ze)
            testing_data = gs_regress(testing_data, xb, xe, yb, ye, zb, ze)

        elif scan_count == 3:

            training1_data = gs_regress(training1_data, xb, xe, yb, ye, zb, ze)
            training2_data = gs_regress(training2_data, xb, xe, yb, ye, zb, ze)
            testing_data = gs_regress(testing_data, xb, xe, yb, ye, zb, ze)

        # #############################################################################
        # Vectorize data into single np array

        listed1 = []
        listed2 = []
        listed_testing = []

        for tr in range(int(training1_data.shape[3])):

            tr_data1 = training1_data[xb:xe, yb:ye, zb:ze, tr]
            vectorized1 = np.array(tr_data1.ravel())
            listed1.append(vectorized1)

            if scan_count == 3:

                tr_data2 = training2_data[xb:xe, yb:ye, zb:ze, tr]
                vectorized2 = np.array(tr_data2.ravel())
                listed2.append(vectorized2)

            te_data = testing_data[xb:xe, yb:ye, zb:ze, tr]
            vectorized_testing = np.array(te_data.ravel())
            listed_testing.append(vectorized_testing)

        train_vectors1 = np.asarray(listed1)
        test_vectors = np.asarray(listed_testing)

        if scan_count == 3:
            train_vectors2 = np.asarray(listed2)

        # #############################################################################
        # Averaging training signal

        averaged_train1 = []
        averaged_train2 = []
        averaged_test = []

        for num in [i*5 for i in range(27)]:

            averaged_train1.append(np.average(train_vectors1[num:num+5], axis=0))

            if scan_count == 3:
                averaged_train2.append(np.average(train_vectors2[num:num+5], axis=0))

        if scan_count == 2:
            train_vectors = np.asarray(averaged_train1)
            print('Has ' + str(scan_count) + ' valid PEER scans')
        elif scan_count == 3:
            train_vectors = np.asarray(averaged_train1 + averaged_train2)
            print('Has ' + str(scan_count) + ' valid PEER scans')

        # #############################################################################
        # Import coordinates for fixations

        fixations = pd.read_csv('stim_vals.csv')
        x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 1)*monitor_width/2, scan_count-1)
        y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 1)*monitor_height/2, scan_count-1)

        # #############################################################################
        # Create SVR Model

        print('making model')

        # GridSearch Model
        GS_model = SVR(kernel='linear')
        parameters = {'kernel': ('linear', 'poly'), 'C': [100, 1000, 2500, 5000, 10000],
                      'epsilon': [.01, .005, .001]}
        clfx = GridSearchCV(GS_model, parameters)
        clfx.fit(train_vectors, x_targets)
        clfy = GridSearchCV(GS_model, parameters)
        clfy.fit(train_vectors, y_targets)
        predicted_x = clfx.predict(test_vectors)
        predicted_y = clfy.predict(test_vectors)

        print('model created')

        # #############################################################################
        # Plot SVR predictions against targets

        plt.figure(figsize=(10, 10))
        subplot_i = 0

        for num in range(27):

            nums = num * 5

            if num not in [18, 25]:

                subplot_i += 1
                plt.subplot(5, 5, subplot_i)
                axes = plt.gca()
                axes.set_xlim([-1500, 1500])
                axes.set_ylim([-1200, 1200])
                plt.scatter(x_targets[num], y_targets[num], color='k', marker='x')
                plt.scatter(predicted_x[nums:nums+5], predicted_y[nums:nums+5], s=5)

            elif num == 18 or num == 25:

                plt.subplot(5, 5, 1)
                axes = plt.gca()
                axes.set_xlim([-1500, 1500])
                axes.set_ylim([-1200, 1200])
                plt.scatter(x_targets[num], y_targets[num], color='k', marker='x')
                plt.scatter(predicted_x[nums:nums+5], predicted_y[nums:nums+5], s=5)

            else:
                continue

        # plt.savefig(os.path.join(output_path, set + '.png'), bbox_inches='tight', dpi=600)
        # plt.show()

        print('Completed participant ' + set)

        # ###############################################################################
        # Get error measurements

        x_res = []
        y_res = []

        for num in range(27):

            nums = num * 5

            for values in range(5):

                error_x = (abs(x_targets[num] - predicted_x[nums + values]))**2
                error_y = (abs(y_targets[num] - predicted_y[nums + values]))**2
                x_res.append(error_x)
                y_res.append(error_y)

        x_error = np.sqrt(np.sum(np.array(x_res))/135)
        y_error = np.sqrt(np.sum(np.array(y_res))/135)

        params.loc[set, 'x_error_gsr'] = x_error
        params.loc[set, 'y_error_gsr'] = y_error
        params.loc[set, 'scan_count'] = scan_count
        params.to_csv('subj_params.csv')

        if scan_count == 3:

            try: # This is included in case the QAP csv doesn't already have the subject processed

                fd1 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_1']['RMSD (Mean)'])
                fd2 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_2']['RMSD (Mean)'])
                fd3 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_3']['RMSD (Mean)'])
                dv1 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_1']['Std. DVARS (Mean)'])
                dv2 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_2']['Std. DVARS (Mean)'])
                dv3 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_3']['Std. DVARS (Mean)'])

                fd_score = np.average([fd1, fd2, fd3])
                dvars_score = np.average([dv1, dv2, dv3])
                params.loc[set, 'mean_fd'] = fd_score
                params.loc[set, 'dvars'] = dvars_score

            except:

                print('Participant not found in QAP')

        elif scan_count == 2:

            try:

                fd1 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_1']['RMSD (Mean)'])
                fd2 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_2']['RMSD (Mean)'])
                dv1 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_1']['Std. DVARS (Mean)'])
                dv2 = float(qap[qap['Participant'] == set][qap['Series'] == 'func_peer_run_2']['Std. DVARS (Mean)'])

                fd_score = np.average([[fd1, fd2]])
                dvars_score = np.average([dv1, dv2])
                params.loc[set, 'mean_fd'] = fd_score
                params.loc[set, 'dvars'] = dvars_score

            except:

                print('Participant not found in QAP')

        params.to_csv('subj_params.csv')

    except:

        print('Error processing participant')

# #############################################################################
# Visualize error vs motion

# params = pd.read_csv('subj_params.csv', index_col='subject')
# params = params[params['x_error'] < 50000][params['y_error'] < 50000][params['mean_fd'] < .30][params['dvars'] < 1.3]
#
# num_part = len(params)
# print(num_part)
#
# x_error_list = params.loc[:, 'x_error'][:num_part].tolist()
# y_error_list = params.loc[:, 'y_error'][:num_part].tolist()
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

# #############################################################################
# Visualization for one participant (per fixation)

# plt.figure()
# axes = plt.gca()
# axes.set_xlim([-1200, 1200])
# axes.set_ylim([-900, 900])
# for num in [0, 3, 5, 7, 10, 15, 21, 24]:
#     nums = num * 5
#     if num not in [18, 25]:
#         plt.scatter(x_targets[num], y_targets[num], color='k', marker='x')
#         plt.scatter(predicted_x[nums:nums+5], predicted_y[nums:nums+5])
# plt.show()

# #############################################################################
# Visualization for one participant in each direction

x_targets = np.repeat(np.array(fixations['pos_x']), 5)*monitor_width/2
y_targets = np.repeat(np.array(fixations['pos_y']), 5)*monitor_height/2

time_series = range(0, 135)

plt.figure()
plt.subplot(2, 1, 1)
plt.ylabel('Horizontal position')
plt.plot(time_series, x_targets, '.-', color='k')
plt.plot(time_series, predicted_x, '.-', color='b')
plt.subplot(2, 1, 2)
plt.ylabel('Vertical position')
plt.xlabel('TR')
plt.plot(time_series, y_targets, '.-', color='k')
plt.plot(time_series, predicted_y, '.-', color='b')
# plt.savefig(os.path.join(output_path, 'y_dir.png'), bbox_inches='tight', dpi=600)
plt.show()

# #############################################################################
# Histogram for RMSE distribution after outlier removal


def remove_out(group):

    temp = params[group][:350].tolist()
    temp = [float(x) for x in temp]
    temp_mean = np.array(temp).mean()
    temp_stdv = np.array(temp).std()
    cap = temp_mean + 3*temp_stdv

    modified_group = [x for x in temp if 0 < x < cap]

    return modified_group

x_no_gsr = remove_out('x_error')
y_no_gsr = remove_out('y_error')
x_gsr = remove_out('x_error_gsr')
y_gsr = remove_out('y_error_gsr')

hist_x, bins_x = np.histogram(x_no_gsr)
hist_y, bins_y = np.histogram(y_no_gsr)
hist_x_gsr, bins_x_gsr = np.histogram(x_gsr)
hist_y_gsr, bins_y_gsr = np.histogram(y_gsr)

plt.figure()
plt.title('Normalized histogram of RMSE')
# plt.bar(bins_x[:-1], hist_x.astype(np.float32) / hist_x.sum(), width=(bins_x[1]-bins_x[0]), color='b', alpha=.5, label='No GSR')
# plt.bar(bins_x_gsr[:-1], hist_x_gsr.astype(np.float32) / hist_x_gsr.sum(), width=(bins_x_gsr[1]-bins_x_gsr[0]), color='r', alpha=.5, label='GSR')
plt.ylabel('Proportion')
plt.xlabel('RMSE (y-direction)')
plt.bar(bins_y[:-1], hist_y.astype(np.float32) / hist_y.sum(), width=(bins_y[1]-bins_y[0]), color='b', alpha=.5, label='No GSR')
plt.bar(bins_y_gsr[:-1], hist_y_gsr.astype(np.float32) / hist_y_gsr.sum(), width=(bins_y_gsr[1]-bins_y_gsr[0]), color='r', alpha=.5, label='GSR')
plt.legend()
plt.savefig(os.path.join(output_path, 'y_dir_histogram'), bbox_inches='tight', dpi=600)
plt.show()


