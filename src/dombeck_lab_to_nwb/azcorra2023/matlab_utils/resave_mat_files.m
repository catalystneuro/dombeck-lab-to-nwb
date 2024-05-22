% Utility function to resave mat files to version 7.3 that are readable in Python
% The root folder path should contain subfolders with mat files to be resaved
% Usage example: resave_mat_files('/Volumes/LaCie/CN_GCP/Dombeck/Azcorra2023/');

function resave_mat_files(root_folder_path)
    % Get a list of all files and folders in this folder.
    all_files = dir(root_folder_path);
    % Extract the names of all files and folders.
    all_names = {all_files.name};
    % Get a logical vector that tells which is a directory.
    dir_flags = [all_files.isdir];
    % Extract the names of all subfolders.
    subfolders = all_names(dir_flags);
    % Print folder names to command window.
    for k = 1 : length(subfolders)
        if strcmp(subfolders{k}, '.') || strcmp(subfolders{k}, '..')
            continue;
        end
        fprintf('Sub folder #%d = %s\n', k, subfolders{k});
        resave_mat_files(fullfile(root_folder_path, subfolders{k}));
    end
    % Get a list of all mat files in the current directory.
    mat_files = dir(fullfile(root_folder_path, 'Binned405_*.mat'));
    % Loop through each mat file in the current directory.
    for k = 1 : length(mat_files)
        mat_file_path = fullfile(root_folder_path, mat_files(k).name);
        fprintf('Resaving mat file #%d = %s\n', k, mat_file_path);
        % Load the mat file.
        load(mat_file_path);

        % Resave the mat file to version 7.3.
        save(mat_file_path, 'T', '-v7.3');
        % Clear the loaded variables.
        clear('T');
        %clear;
    end
end
