import operator

import can
import flask
import pathlib
import os
import shutil
import threading
import tarfile
from PIL import Image, ImageEnhance, ImageFilter
import json
import moviepy.editor as moviepy
from app import app
from flask import render_template
from textwrap import wrap
from flask_sse import sse
import time
import re
import gevent


path = pathlib.Path(os.path.dirname(os.path.realpath(__file__))).parent
analysis_path = f"/static/analysis/"
vin = ""
parsed_file = {}
streaming = False
startingIdx = 0
selected_path = []
current_path = ""
folder_to_load = ""
looping = False
existing_to_load = []
unchanged_log_rows = {}
log_offset_percent = 0
stream_end_reached = False
file_parsing_finished = False
files_to_unpack = 0
files_unpacked = 0
log_timespan = 0
length_of_log = 0
playback_speed = 1
freq_stored_values = {}
scalers_dict = {}
uppy_bank = {}


# NOTE FOR SCALERS: APPLY SCALE FIRST THEN OFFSET FORMULA IS , VALUE = (RAW*SCALE) + OFFSET

@app.route('/', methods=["GET", "POST"])
def index():
    global vin
    global path
    global selected_path
    global current_path
    global folder_to_load
    global analysis_path
    global param_name
    global existing_to_load
    global unchanged_log_rows

    current_path = '/mnt/san'
    # current_path = '/mnt/c/Users/tom/Documents'
    # Initial Page Load
    if flask.request.method == "GET":
        selected_path = []
        roots = []
        for whole_path in os.listdir(current_path):
            selected_path.append(whole_path)

        get_existing()
        return flask.render_template('carhax.html',
                                     selected_path=selected_path,
                                     current_path=current_path,
                                     existing=existing_to_load,
                                     title='Carhax File Browser')

    # After first selection of primary directory
    if flask.request.method == "POST":
        print(folder_to_load)
        uniques = []
        if 'folder_vin' in flask.request.form:
            all_logs = []
            all_videos = []
            main_path = (pathlib.Path(os.path.dirname(os.path.realpath(__file__))).parent)
            for file in os.listdir(f"{main_path}{folder_to_load}"):
                if '.mp4' in file or '.avi' in file or '.tar' in file:
                    all_videos.append(file)
                if '.log' in file:
                    all_logs.append(file)
            get_existing()

            for log in all_logs:
                uniques.append({log: get_uniques(f"{main_path}{folder_to_load}/{log}")})
                unchanged_log_rows = {}
        title = folder_to_load.split("/")[4]
        return render_template('carhax.html', folder_to_load=folder_to_load, all_logs=all_logs, all_videos=all_videos,
                               existing=existing_to_load, uniques=uniques, title=title)

    return render_template('carhax.html')


@app.route('/carhax/load_folder', methods=["POST"])
def load_folder():
    global analysis_path
    global folder_to_load
    global path
    global vin
    global param_name

    load_in_scale_list()

    vin = ""
    requested_path = json.loads(flask.request.data)['path']
    if 'analysis' in requested_path:
        vin = requested_path.split("/")[-2]
        param_name = requested_path.split("/")[-1]
        folder_to_load = f"{analysis_path}{vin}/{param_name}"
        return "Success"

    for i, name in enumerate(requested_path.split("/")):
        if 'apture' in name:
            vin = requested_path.split("/")[i-1]
            break
    if vin == "":
        return "Broken"

    for paths, subdirs, files in os.walk(requested_path):
        for file in files:
            if '.mp4' in file or '.avi' in file:
                load_with_video(requested_path)
                return "Success"

            if '.tar' in file:
                load_with_tar(requested_path)
                return "Success"
    return "Success"


def load_with_tar(requested_path):
    global path
    global vin
    global param_name
    global folder_to_load

    all_logs = []
    all_videos = []
    error_files = []
    vin = requested_path.split("/")[-3]
    param_name = requested_path.split("/")[-1]
    print('req path: ' , requested_path)
    vin_path = f"{path}{analysis_path}{vin}"
    print("vin path: " + vin_path)

    if not os.path.exists(f"{vin_path}/{param_name}"):
        pathlib.Path(f"{vin_path}/{param_name}").mkdir(parents=True)

    for paths, subdirs, files in os.walk(requested_path):
        for file in files:
            print(file)
            if file not in os.listdir(f"{vin_path}/{param_name}"):
                if 'videos' in paths:
                    param_name = paths.split("/")[-2]
                    if not os.path.exists(f"{vin_path}/{param_name}") and param_name != "":
                        pathlib.Path(f"{vin_path}/{param_name}").mkdir(parents=True)

            if 'tar' in file:
                shutil.copy2(f"{requested_path}/videos/{file}", f"{vin_path}/{param_name}/{file}")

            if 'log' in file:
                param_name = paths.split("/")[-1]
                if not os.path.exists(f"{vin_path}/{param_name}") and param_name != "":
                    pathlib.Path(f"{vin_path}/{param_name}").mkdir(parents=True)
                shutil.copy2(f"{requested_path}/{file}", f"{vin_path}/{param_name}/{file}")
                all_logs.append(file)
            for file in os.listdir(f"{vin_path}/{param_name}"):
                if '.log' not in file:
                    all_videos.append(file)
                if '.log' in file:
                    all_logs.append(file)
            folder_to_load = f"{analysis_path}{vin}/{param_name}"



def load_with_video(requested_path):
    global path
    global vin
    global param_name
    global folder_to_load

    all_logs = []
    all_videos = []
    error_files = []
    vin = requested_path.split("/")[-3]
    param_name = requested_path.split("/")[-1]
    print('req path: ' , requested_path)
    vin_path = f"{path}{analysis_path}{vin}"
    print("vin path: " + vin_path)

    if not os.path.exists(f"{vin_path}/{param_name}"):
        pathlib.Path(f"{vin_path}/{param_name}").mkdir(parents=True)

    for paths, subdirs, files in os.walk(requested_path):
        for file in files:
            print(file)
            if file not in os.listdir(f"{vin_path}/{param_name}"):
                if 'videos' in paths:
                    param_name = paths.split("/")[-2]
                    if not os.path.exists(f"{vin_path}/{param_name}") and param_name != "":
                        pathlib.Path(f"{vin_path}/{param_name}").mkdir(parents=True)

            if '.mp4' in file or '.avi' in file:
                print(file)
                try:
                    new_filename = ""
                    if '.avi' in str(file):
                        new_filename = str(file).replace(".avi", ".mp4")
                    clip = moviepy.VideoFileClip(f"{requested_path}/videos/{file}")
                    if new_filename != "":
                        clip.write_videofile(f"{vin_path}/{param_name}/{new_filename}", codec="libx264")
                    else:
                        clip.write_videofile(f"{vin_path}/{param_name}/{file}", codec="libx264")
                except Exception as e:
                    print(e)
                    error_files.append(f"{requested_path}/videos/{file}")

            if 'log' in file:
                param_name = paths.split("/")[-1]
                if not os.path.exists(f"{vin_path}/{param_name}") and param_name != "":
                    pathlib.Path(f"{vin_path}/{param_name}").mkdir(parents=True)
                shutil.copy2(f"{requested_path}/{file}", f"{vin_path}/{param_name}/{file}")
                all_logs.append(file)
            for file in os.listdir(f"{vin_path}/{param_name}"):
                if '.log' not in file:
                    all_videos.append(file)
                if '.log' in file:
                    all_logs.append(file)
            folder_to_load = f"{analysis_path}{vin}/{param_name}"
            # ocr_test()
    return "Success"


@app.route('/carhax/load_initial/<filename>', methods=["GET"])
def load_initial(filename):
    global parsed_file
    global vin
    global file_parsing_finished
    global log_timespan
    global length_of_log
    global scalers_dict

    file_parsing_finished = False
    starting_timestamp = 0
    ending_timestamp = 0
    main_path = (pathlib.Path(os.path.dirname(os.path.realpath(__file__))).parent)
    parsed_file = {}
    info = {}
    file = f'{main_path}{analysis_path}{vin}/{param_name}/{filename}'
    print("file to load : ", file)
    num_lines = sum(1 for line in open(file))
    with open(file, 'r') as f:
        for i, line in enumerate(f):
            try:
                parsed_line = []
                timestamp = line.split(" ")[0]
                if i == 0:
                    starting_timestamp = float(timestamp.replace("(", "").replace(")", ""))
                if i == num_lines-2:
                    ending_timestamp = float(timestamp.replace("(", "").replace(")", ""))
                network = line.split(' ')[1]
                data = line.split(" ")[2].split("#")[1]
                arb_id = line.split(" ")[2].split("#")[0]
                parsed_line.append(timestamp)
                parsed_line.append(network)
                parsed_line.append(arb_id)
                data_bytes = wrap(data, 2)
                parsed_line.append(data_bytes)
                parsed_file[i] = parsed_line
            except Exception as e:
                print("missed line - ", i)
                continue

    length_of_log = len(list(parsed_file))
    log_timespan = round(float(ending_timestamp - starting_timestamp), 5)
    print("length of log", len(list(parsed_file)))
    print("log timespan ", log_timespan)
    info['ending_timestamp'] = float(ending_timestamp)
    info['starting_timestamp'] = float(starting_timestamp)
    info['timestamp_diff'] = log_timespan
    info['log_length'] = length_of_log
    info['scalers'] = scalers_dict
    info['full_log'] = parsed_file
    file_parsing_finished = True
    final = sorted(parsed_file.items(), key=lambda item: float(item[1][0].replace("(", "").replace(")","")))
    new_parsed_file = {}
    for i, line in enumerate(final):
        new_parsed_file[i] = final[i][1]
    parsed_file = {}
    parsed_file = new_parsed_file

    return info

@app.route("/carhax/stop_stream")
def stop_stream():
    global streaming
    streaming = False
    return""

curr_idx = 0
@app.route("/carhax/start_stream/<starting_timestamp>/<playback>")
def start_stream(starting_timestamp, playback):
    global streaming
    global parsed_file
    global startingIdx
    global log_offset_percent
    global stream_end_reached
    global curr_idx
    global playback_speed

    playback_speed = float(playback)
    # print("starting idx: ", starting_timestamp)
    a = []
    for key, value in list(parsed_file.items()):
        a.append(float(value[0].split(" ")[0].replace("(", "").replace(")", "")))

    # print("log length : ", len(a))
    startingIdx = min(range(len(a)), key=lambda i: abs(a[i] - float(starting_timestamp)))
    curr_idx = startingIdx
    # print('starting stream starting idx: ' ,startingIdx)
    # print(str(f"{len(parsed_file)},{startingIdx}"))
    stream_end_reached = False
    streaming = True
    return str(f"{len(parsed_file)},{startingIdx}")


@app.route('/carhax/stream_data')
def stream_data():
    global streaming
    while True:
        if streaming:
            # sse.publish(get_stream_data(), type='message')
            # return ""
            return flask.Response(get_stream_data(), mimetype="text/event-stream")
        # sse.publish(wait(), type='message')
        # return ""
        return flask.Response(wait(), mimetype="text/event-stream")


def wait():
    global streaming
    while True:
        if streaming:
            break
        yield f"data:waiting\n\n"
        gevent.sleep(0.1)

    yield f"data:starting\n\n"
    gevent.sleep(0.1)




def get_stream_data():
    global parsed_file
    global streaming
    global looping
    global log_offset_percent
    global stream_end_reached
    global log_timespan
    global curr_idx
    global length_of_log
    global playback_speed

    time_between = ((log_timespan/(length_of_log/60))/60) / playback_speed
    while True:
        if not streaming:
            break
        if stream_end_reached: return ""

        outgoing_data = {}
        if curr_idx == length_of_log:
            print("---Reached End-----")
            streaming = False
            break

        if not looping and stream_end_reached:
            print("--END--")
            streaming = False

        outgoing_data['data'] = json.dumps(parsed_file[int(curr_idx)])
        outgoing_data['status'] = streaming
        outgoing_data['looping'] = looping
        outgoing_data['end'] = stream_end_reached
        outgoing_data['current_idx'] = curr_idx
        curr_idx += 1
        yield f"data:{json.dumps(outgoing_data)}\n\n"
        time.sleep(time_between)

    yield f"data:stopping\n\n"
    time.sleep(0.1)


@app.route('/carhax-settings', methods=["POST"])
def carhax_setting():
    global looping

    data =  flask.jsonify(flask.request.json).get_json()
    looping = bool(data['looping'])

    return ""

@app.route("/carhax-get-new-idx/<videoLoc>", methods=["GET"])
def carhax_new_idx(videoLoc):
    global parsed_file
    global startingIdx

    # print(f'starting ix {startingIdx}')
    parsed_line_idx = int(len(parsed_file) * float(videoLoc))
    # print(f"parsed idx: {parsed_line_idx}")
    timestamp_of_line = parsed_file[parsed_line_idx][0]
    print(timestamp_of_line)
    return str(timestamp_of_line)


@app.route('/carhax/get_folder_contents/<new_path>', methods=["GET"])
def get_folder_contents(new_path):
    global current_path

    nested = []
    next_path = current_path + f"/{new_path}"
    for item in os.listdir(next_path):
        nested.append(f"{next_path}/{item}")

    current_path = next_path
    return flask.jsonify(nested)

@app.route('/carhax/direct_navigate', methods=["POST"])
def direct_navigate():
    global current_path

    data = json.loads(flask.request.data)
    current_path = data['path']
    items = []
    for item in os.listdir(current_path):
        items.append(item)
    return flask.jsonify(items)


@app.route('/carhax/remove_quickjump', methods=['POST'])
def remove_quickjump():
    param_route = json.loads(flask.request.data)['path']
    if os.path.exists(param_route):
        shutil.rmtree(param_route)
        return flask.jsonify({'status': True})
    else:
        return flask.jsonify({'status': False})


def get_existing():
    global existing_to_load
    global path
    global analysis_path

    existing_to_load = []

    for vin in os.listdir(f"{path}{analysis_path}"):
        whole_path = f"{path}{analysis_path}{vin}"
        for param_folder in os.listdir(whole_path):
            existing_to_load.append({str(vin): param_folder, "whole_path": f"{whole_path}/{param_folder}"})



def get_uniques(filename):
    uniques = {}
    with open(filename) as f:
        lines = f.readlines()
        for l in lines:
            line = l.split(" ")
            try:
                can = line[1]
                arb = line[2][:3]
                if can not in uniques:
                    uniques[can] = [arb]
                else:
                    if arb not in uniques[can]:
                        uniques[can].append(arb)
            except IndexError:
                continue

    stored = {}
    for v in uniques.values():
        for i in v:
            if i in stored:
                stored[i] += 1
            else:
                stored[i] = 1

    final = {}
    for k, v in stored.items():
        if v == 1:
            for s, t in uniques.items():
                for h in t:
                    if h == k:
                        if s not in final:
                            final[s] = [k]
                        else:
                            final[s].append(k)
    return final


# ----- FREQUENCY STUFF ---------

@app.route('/carhax/get_unchanged')
def get_unchanged():
    # global unchanged_log_rows
    #
    # if len(unchanged_log_rows) > 0:
    #     return True

    stored = get_log_occurrences(0,0)
    zero_changes = []
    for key, value in stored.items():
        found = True
        for val in value['data']:
            check_val = (list(val.values())[0])
            if check_val != 0:
                found = False
                break
        if found:
            zero_changes.append(f"{value['can']}-{value['arb']}")
    # print(zero_changes)
    return json.dumps(zero_changes)

@app.route('/carhax/analyze_freq/<num>/<starting_timestamp>/<ending_timestamp>/<new_check>')
def freq_analysis(num, starting_timestamp, ending_timestamp, new_check):
    global freq_stored_values

    if new_check == 'true':
        print('resetting values')
        freq_stored_values = {}

    num_to_check = int(num)

    a = []
    for key, value in list(parsed_file.items()):
        a.append(float(value[0].split(" ")[0].replace("(", "").replace(")", "")))

    startingIdx = min(range(len(a)), key=lambda i: abs(a[i] - float(starting_timestamp)))
    endingIdx = min(range(len(a)), key=lambda i: abs(a[i] - float(ending_timestamp)))

    print(startingIdx, endingIdx, "<------")
    stored = get_log_occurrences(startingIdx, endingIdx)
    found_values = {}
    for key, value in stored.items():
        for i in value['data']:
            for k in i.values():
                if k == num_to_check:
                    for kk,vv in list(value['timestamps'].items()):
                        if len(vv) != num_to_check:
                            value['timestamps'].pop(kk)
                    found_values[key] = value

    freq_stored_values = found_values
    return found_values


@app.route('/carhax/get_unchanged_inloop/<start>/<end>')
def get_unchanged_inloop(start, end):
    global parsed_file

    start_line = int(carhax_new_idx(start))
    end_line = int(carhax_new_idx(end))

    stored = get_log_occurrences(start_line, end_line)
    print('initial len, ', len(list(stored)))
    zero_changes = []
    for key, value in stored.items():

        found = True
        for val in value['data']:
            check_val = (list(val.values())[0])
            if check_val != 0:
                found = False
                break
        if found:
            zero_changes.append(f"{value['can']}-{value['arb']}")

    return json.dumps(zero_changes)


@app.route('/carhax/scale_value_find/<vals>/<width>/<endian>')
def scale_value_find(vals, width, endian):
    width = int(width)
    binary_data = {}
    for i, line in enumerate(list(parsed_file)):
        bytes = parsed_file[i][3]
        bit_array = []
        for hex in bytes:
            bit_array.append(bin(int(hex, 16))[2:].zfill(8))
        binary_data[line] = "".join(bit_array)

    vals_to_search = []
    for val in vals.split(","):
        val_to_search = None
        if val != "":
            val_binary = bin(int(val, 10))[2:]
            if endian == "big":
                val_to_search = val_binary.zfill((width))
            else:
                val_to_search = val_binary.ljust(width, "0")
        vals_to_search.append(val_to_search)

    found = {}
    for k, val in enumerate(vals_to_search):
        for i, binary in enumerate(list(binary_data)):
            if val in binary_data[i]:
                network = parsed_file[i][1]
                arb = parsed_file[i][2]
                pos =  binary_data[i].find(val)
                loc = f"{network}-{arb}-{pos}"
                if loc not in found:
                    found[loc] = {
                        'lines': 1,
                        'hits': [vals_to_search[k]]
                    }
                else:
                    if vals_to_search[k] in found[loc]['hits']:
                        found[loc]['lines'] += 1
                    else:
                        found[loc]['hits'].append(vals_to_search[k])


    all_found = {}
    partial_found = {}
    for key, val in found.items():
        if len(val['hits']) == len(vals.split(",")):
            all_found[key] = val
        elif len(val['hits']) > 1:
            partial_found[key] = val

    final = sorted(all_found.items(), key=lambda item: item[1]['lines'], reverse=True)
    # print(list(final)[:25])
    return flask.json.dumps(list(final)[:25])



def get_timestamp_index(timestamp):
    a = []
    for key, value in list(parsed_file.items()):
        a.append(float(value[0].split(" ")[0].replace("(", "").replace(")", "")))

    ts = (min(range(len(a)), key=lambda i: abs(a[i] - float(timestamp))))

    return ts


def carhax_new_idx(videoLoc):
    global parsed_file
    global startingIdx

    parsed_line_idx = int(len(parsed_file) * float(videoLoc))

    return str(parsed_line_idx)

def get_log_occurrences(start, end):
    global parsed_file
    global freq_stored_values

    stored = {}

    # print(freq_stored_values)
    # print('start', start, 'end', end)
    count = 0
    for key, value in parsed_file.items():

        if start != end:
            if start > count or end < count:
                count += 1
                continue

        timestamp = value[0]
        can = value[1]
        arb = value[2]
        data = value[3]

        if f"{can}-{arb}" not in freq_stored_values.keys() and len(freq_stored_values) > 0:
            continue

        data_info = []
        uid = f"{can}-{arb}"
        if uid not in stored:
            for data_byte in data:
                add = {data_byte: 0}
                data_info.append(add)
            stored[uid] = {'timestamps': {}, 'can': can, 'arb': arb, 'data': data_info}
            count += 1
        else:

            if len(data) > len(stored[uid]['data']):
                for i in range(len(stored[uid]['data']), len(data)):
                    stored[uid]['data'].insert(i, {data[i]: 1})

            elif len(data) < len(stored[uid]['data']):
                for i in range(len(data), len(stored[uid]['data'])):
                    if list(stored[uid]['data'][i].keys())[0] == "":
                        break
                    new_value_changed = list(stored[uid]['data'][i].values())[0] + 1
                    stored[uid]['data'].insert(i, {"": new_value_changed})
                    stored[uid]['data'].pop(i + 1)

            for i, byte in enumerate(list(stored[uid]['data'])):

                if i > len(data)-1:
                    break

                if data[i] != list(stored[uid]['data'][i].keys())[0]:
                    new_value = list(stored[uid]['data'][i].values())[0] + 1
                    stored[uid]['data'].insert(i, {data[i]: new_value})
                    stored[uid]['data'].pop(i+1)

                    if i not in stored[uid]['timestamps']:
                        stored[uid]['timestamps'][i] = [timestamp]
                    else:
                        stored[uid]['timestamps'][i].append(timestamp)
            count += 1
    # print('final count', count)
    # print('length of return', len(stored))
    return stored


@app.route('/carhax/unpack_tar/<video_file>')
def unpack_tar_video(video_file):
    global folder_to_load
    global path
    global file_parsing_finished
    global parsed_file
    global files_to_unpack
    global files_unpacked

    files_to_unpack = 0
    files_unpacked = 0

    while not file_parsing_finished:
        time.sleep(.25)


    file_list = []
    file_to_unpack = f"{path}{folder_to_load}/{video_file}"
    subfolder = file_to_unpack.split('-')[0].replace(".tar", "")


    if not os.path.exists(f"/{subfolder}"):
        pathlib.Path(f"{subfolder}").mkdir(exist_ok=True)
        a = []
        for key, value in list(parsed_file.items()):
            a.append(float(value[0].split(" ")[0].replace("(", "").replace(")", "")))

    else:
        for image in os.listdir(f"/{subfolder}"):
            file_list.append(image)
        print(len(file_list))
        files_to_unpack = 1
        files_unpacked = 1
        return json.dumps({'file_list': file_list, 'folder': f"/{subfolder}"})

    tf = tarfile.open(file_to_unpack)
    try:
        tf.extractall(f"/{subfolder}")
    except Exception as e:
        print(f"--------{e}------------")
    tf.close()
    all_images = []
    for image in os.listdir(f"/{subfolder}"):
        all_images.append(image)

    all_images.sort(key=lambda f: int(re.sub('\D', '', f)))
    files_to_unpack = len(all_images)
    sum_of_section = 0
    section_counter = 0
    avg_of_section = 0
    for i, image in enumerate(all_images):
        section_counter += 1
        files_unpacked += 1
        if i % 100 == 0:
            print(i)
        old_id = str(image).replace("_", ".").replace(".jpg", "")
        try:
            closest_idx = parsed_file[min(range(len(a)), key=lambda i: abs(a[i] - float(old_id)))][0]
        except KeyError:
            continue
        new_name = str(closest_idx).replace(".", "_").replace(")", "").replace("(", "") + '.jpg'
        os.rename(f"/{subfolder}/{image}", f"{subfolder}/{new_name}")
        file_list.append(new_name)


    return json.dumps({'file_list': sorted(file_list), 'folder': f"/{subfolder}"})


@app.route("/carhax/unpack_progress")
def unpack_progress():
    global files_unpacked
    global files_to_unpack

    if files_to_unpack == 0:
        time.sleep(1)

    return json.dumps({'files_to_unpack': files_to_unpack, 'files_unpacked': files_unpacked})


def load_in_scale_list():
    global scalers_dict

    scaler_csv = open(f"{pathlib.Path(__file__).parent.parent}/static/scale_list.csv")
    lines = scaler_csv.readlines()
    for i, line in enumerate(lines):
        if i == 0:
            continue
        scale = line.split(",")[0]
        offset = line.split(",")[1]
        width = line.split(",")[2]
        unit = line.split(",")[3]

        if unit not in scalers_dict:
            scalers_dict[unit] = {
                'scales': [scale],
                'offsets': [offset],
                'widths': [width]
            }
        else:
            scalers_dict[unit]['scales'].append(scale)
            scalers_dict[unit]['offsets'].append(offset)
            scalers_dict[unit]['widths'].append(width)



    # ----- OLD SCALED VALUE CODE .. PROBABLY DELETE -----------------
    # binary_data = {}
    # for i, line in enumerate(list(parsed_file)):
    #     bytes = parsed_file[i][3]
    #     bit_array = []
    #     for hex in bytes:
    #         bit_array.append(bin(int(hex, 16))[2:].zfill(8))
    #     binary_data[line] = "".join(bit_array)

    # positions = {}
    # possiblities = {}
    # initial_search_binary= []
    #
    # # GENERATE BASIC BINARIES FROM FIRST VALUE
    # print("Generating First Values")
    # if unit in scalers_dict:
    #     for scale in scalers_dict[unit]['scales']:
    #         scaled_decimal = (float(value_list[0]) / float(scale))
    #         for offset in scalers_dict[unit]['offsets']:
    #             offset_scaled = float(scaled_decimal) - float(offset)
    #             if offset_scaled.is_integer():
    #                 offset_val_to_search = (bin(int(offset_scaled))[2:].zfill(8))
    #                 initial_search_binary.append(offset_val_to_search)
    #
    #
    # initial_search_binary = list(set(initial_search_binary))
    # # FIND ALL POSITIONS FOR MATCHING POSSIBLE BINARIES
    # print("Finding Positions")
    # for i, line in enumerate(list(binary_data)):
    #     for binary in initial_search_binary:
    #         if binary in binary_data[i]:
    #             pos = binary_data[i].find(binary)
    #             network = parsed_file[i][1]
    #             arb = parsed_file[i][2]
    #             positions[f"{network}-{arb}"] = pos
    #
    #
    # secondary_binary = []
    # # GENERATE BINARY FOR FOLLOWING SEARCHES
    # print("Generating All Other Binaries To Search")
    # for i, val in enumerate(value_list):
    #     if i == 0:
    #         continue
    #     if unit in scalers_dict:
    #         for scale in scalers_dict[unit]['scales']:
    #             scaled_decimal = (float(value_list[i]) / float(scale))
    #             for offset in scalers_dict[unit]['offsets']:
    #                 offset_scaled = float(scaled_decimal) - float(offset)
    #                 if offset_scaled.is_integer():
    #                     offset_val_to_search = (bin(int(offset_scaled))[2:].zfill(8))
    #                     secondary_binary.append(offset_val_to_search)
    #
    #
    # secondary_binary = list(set(secondary_binary))
    # print("Searching through all secondary Binary")
    # for i, line in enumerate(list(binary_data)):
    #     if f"{parsed_file[i][1]}-{parsed_file[i][2]}" not in positions:
    #         continue
    #     for sb in secondary_binary:
    #         if sb in binary_data[i]:
    #             s_pos = binary_data[i].find(sb)
    #             if s_pos == positions[f"{parsed_file[i][1]}-{parsed_file[i][2]}"]:
    #                 if f"{parsed_file[i][1]}-{parsed_file[i][2]}-{s_pos}" not in possiblities:
    #                     possiblities[f"{parsed_file[i][1]}-{parsed_file[i][2]}-{s_pos}"] = 1
    #                 else:
    #                     possiblities[f"{parsed_file[i][1]}-{parsed_file[i][2]}-{s_pos}"] += 1
    #
    #
    # vals_list = []
    # for key, value in list(possiblities.items()):
    #     if value <= 1:
    #         possiblities.pop(key)
    #     else:
    #         vals_list.append(value)
    #
    # new_list = sorted(vals_list)
    # new_list.reverse()
    # final_list = new_list[:10]
    # top_10 = []
    # for key, value in possiblities.items():
    #     if value in final_list:
    #         top_10.append([key, value])
    #
    # print(top_10)

    # @app.route('/carhax/uppy_downy/<type>/<timestamp>')
    # def uppy_downy(type, timestamp):
    #     global parsed_file
    #     global uppy_bank
    #
    #     min = get_timestamp_index(float(timestamp) - 0.25)
    #     max = get_timestamp_index(float(timestamp) + 0.25)
    #
    #     if type == 'start':
    #         uppy_bank = {}
    #         for i, line in enumerate(list(parsed_file)):
    #             if i < min or i > max:
    #                 continue
    #             network = parsed_file[i][1]
    #             arb = parsed_file[i][2]
    #             data = parsed_file[i][3]
    #             uppy_bank[f"{network}-{arb}"] = data
    #         print(len(uppy_bank))
    #         return str(len(uppy_bank))
    #
    #     if type == 'up':
    #         to_remove = []
    #         check_against = []
    #         for i, line in enumerate(list(parsed_file)):
    #             if i < min or i > max:
    #                 continue
    #             check_against.append(parsed_file[i][3])
    #
    #         for i , v in enumerate(list(uppy_bank)):
    #             down_count = 0
    #             # print(list(uppy_bank.values())[i])
    #             # print(check_against[i])
    #             for k, info in enumerate(check_against[i]):
    #                 try:
    #                     # print('comparing : ' , list(uppy_bank.values())[i][k], "----", check_against[i][k])
    #                     if hex(int(check_against[i][k], 16)) > hex(int(list(uppy_bank.values())[i][k], 16)):
    #                         down_count += 1
    #                 except IndexError:
    #                     continue
    #             if down_count >= len(check_against[i]):
    #                 to_remove.append(list(uppy_bank.keys())[i])
    #
    #         for thing in to_remove:
    #             uppy_bank.pop(thing)
    #         print(len(uppy_bank))
    #         return ""
    #
    #     if type == 'down':
    #         to_remove = []
    #         check_against = []
    #         for i, line in enumerate(list(parsed_file)):
    #             if i < min or i > max:
    #                 continue
    #             check_against.append(parsed_file[i][3])
    #
    #         for i , v in enumerate(list(uppy_bank)):
    #             up_count = 0
    #             # print(list(uppy_bank.values())[i])
    #             # print(check_against[i])
    #             for k, info in enumerate(check_against[i]):
    #                 try:
    #                     # print('comparing : ' , list(uppy_bank.values())[i][k], "----", check_against[i][k])
    #                     if hex(int(check_against[i][k], 16)) < hex(int(list(uppy_bank.values())[i][k], 16)):
    #                         up_count += 1
    #                 except IndexError:
    #                     continue
    #             if up_count >= len(check_against[i]):
    #                 to_remove.append(list(uppy_bank.keys())[i])
    #
    #         for thing in to_remove:
    #             uppy_bank.pop(thing)
    #         print(len(uppy_bank))
    #         return ""
    #
    #     if type == 'same':
    #         to_remove = []
    #         check_against = []
    #         for i, line in enumerate(list(parsed_file)):
    #             if i < min or i > max:
    #                 continue
    #             check_against.append(parsed_file[i][3])
    #
    #         for i , v in enumerate(list(uppy_bank)):
    #             same_count = 0
    #             # print(list(uppy_bank.values())[i])
    #             # print(check_against[i])
    #             for k, info in enumerate(check_against[i]):
    #                 try:
    #                     # print('comparing : ' , list(uppy_bank.values())[i][k], "----", check_against[i][k])
    #                     if hex(int(check_against[i][k], 16)) == hex(int(list(uppy_bank.values())[i][k], 16)):
    #                         same_count += 1
    #                 except IndexError:
    #                     continue
    #                 if same_count >= len(check_against[i]):
    #                     to_remove.append(list(uppy_bank.keys())[i])
    #
    #         for thing in to_remove:
    #             uppy_bank.pop(thing)
    #         print(len(uppy_bank))
    #         return ""
