% Utility function to convert data6 table to individual .mat files that are readable in Python

function convert_data6(source_path, output_folder)
    % Load source data
    data6_in = load(source_path, 'data6');
    data6_in = data6_in.data6;

    % Get the size of the table
    [numRows, numColumns] = size(data6_in);

    % Create output folder if it doesn't exist
    if ~exist(output_folder, 'dir')
        mkdir(output_folder);
    end

    for row = 1:numRows
        data6 = struct();
        for column = 1:numColumns
            val = data6_in{row, column};
            column_name = data6_in.Properties.VariableNames{column};
            if iscell(val)
                % Get the first element of the cell array
                val = val{1};
            end

            % Convert MATLAB string variable to char array
            if isstring(val) || ischar(val)
                val = char(val);
            end

            % Check if the column name is "data"
            if strcmp(column_name, 'data')
                % Check if val is a table
                if istable(val)
                    % Flatten the table contents into structArray
                    tableRow = struct();
                    tableColumns = val.Properties.VariableNames;
                    for k = 1:numel(tableColumns)
                        if iscell(val{1, k})
                            % Get the first element of the cell array
                            unpacked_cell = val{1, k}{1};
                            tableRow.(tableColumns{k}) = unpacked_cell;
                        else
                            tableRow.(tableColumns{k}) = val{1, k};
                        end
                    end

                    data6.data = tableRow;
                else
                    data6.(column_name) = val;
                end
            else
                data6.(column_name) = val;
            end

        end

        filename = fullfile(output_folder, sprintf('%s.mat', data6_in.data{row}.Properties.RowNames{1}));
        save(filename, 'data6', '-v7.3');
    end
end
