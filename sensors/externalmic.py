import os
import shutil
import logging
import datetime
from buggd.apps.buggd.utils import call_cmd_line
from buggd.drivers.soundcard import Soundcard
from .option import set_option
from .sensorbase import SensorBase

logger = logging.getLogger(__name__)
class ExternalMic(SensorBase):

    def __init__(self, config=None):
        """
        A class to record audio from the versatile external microphone interface

        Args:
            config: A dictionary loaded from a config JSON file used to replace
            the default settings of the sensor.
        """

        logger.info('Initialising the soundcard')
        self.soundcard = Soundcard()

        call_cmd_line('sudo killall arecord')

        # Initialise the sensor config, double checking the types of values. This
        # code uses the variables named and described in the config static to set
        # defaults and override with any passed in the config file.
        opts = self.options()
        opts = {var['name']: var for var in opts}

        self.record_length = set_option('record_length', config, opts)
        self.record_freq = set_option('record_freq', config, opts)
        self.compress_data = set_option('compress_data', config, opts)
        self.amplification = set_option('amplification', config, opts)
        self.capture_delay = set_option('capture_delay', config, opts)
        self.capture_card = set_option('capture_card', config, opts)
        self.gain = set_option('gain', config, opts)
        self.phantom_power = set_option('phantom_power', config, opts)
        self.enable_internal_mic = set_option('enable_internal_mic', config, opts)
        self.channels = 2 if self.enable_internal_mic else 1

        # set internal variables and required class variables
        self.working_file = 'currentlyRecording.wav'
        self.rec_start_trim_secs = 1 # To remove popping from start of audio recordings
        self.working_dir = None
        self.data_dir = None
        self.server_sync_interval = self.record_length + self.capture_delay

        # Power on the soundcard, with phantom power off and gain set to 0dB
        self.soundcard.enable_external_channel()
        self.soundcard.set_gain(self.gain)
        self.soundcard.set_phantom(self.phantom_power)

        # Power on the internal microphone if required
        if self.enable_internal_mic:
            self.soundcard.enable_internal_channel()
            
    @staticmethod
    def options():
        """
        Static method defining the config options and defaults for the sensor class
        """
        return [{'name': 'record_length',
                 'type': int,
                 'default': 1200,
                 'prompt': 'What is the time in seconds of the audio segments?'},
                {'name': 'record_freq',
                 'type': int,
                 'default': 44100,
                 'prompt': 'At what frequency should we sample from the ADC?'},
                {'name': 'compress_data',
                 'type': bool,
                 'default': True,
                 'prompt': 'Should the audio data be compressed from WAV to VBR mp3?'},
                {'name': 'amplification',
                 'type': int,
                 'default': 1,
                 'prompt': 'By what factor should the audio be amplified by?'},
                {'name': 'capture_delay',
                 'type': int,
                 'default': 0,
                 'prompt': 'How long should the system wait between audio samples?'},
                {'name': 'capture_card',
                 'type': int,
                 'default': 0,
                 'prompt': 'What is the audio recording card number? (arecord --list-devices)'},
                {'name': 'gain',
                 'type': int,
                 'default': 0,
                 'prompt': 'What is the gain of the soundcard? (0-20, 3dB steps)'},
                {'name': 'phantom_power',
                 'type': str,
                 'default': 'none',
                 'prompt': '\'NONE\', \'PIP\' = Plug In Power, \'P3V3\' = 3.3V on M12 Pin 4, \'P48\' = 48V - WARNING: high voltage - check compatibility before connecting microphone'},
                {'name': 'enable_internal_mic',
                 'type': bool,
                 'default': False,
                 'prompt': 'Should the internal microphone be enabled on the other channel?'}
                ]


    def setup(self):
        return True


    def capture_data(self, working_dir, data_dir):
        """
        Method to capture raw (uncompressed) audio data from the I2S Mic

        Args:
            working_dir: A working directory to use for the recorded uncompressed file
            data_dir: The directory to write the final data file to
        """

        # populate the working and upload directories
        self.working_dir = working_dir
        self.data_dir = data_dir

        # Name files by start time and duration (accounting for time stripped from the start of the recording)
        start_time_dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=self.rec_start_trim_secs)
        start_time = start_time_dt.isoformat()[:-3]+'Z' # Remove extra millisecond accuracy and add Z to denote UTC timezone
        start_time = start_time.replace(':','_') # Replace colons with dots (can't have colon in filenames)
        uncomp_f_name = '{}'.format(start_time)

        # Create appropriate message for the log
        if self.enable_internal_mic:
            what = 'stereo from internal and external microphones'
        else:
            what = 'mono from external microphone'
        # Record for a specific duration

        logger.info('Started recording {} at {} for {}s'.format(what, start_time, self.record_length))
        wfile = os.path.join(self.working_dir, self.working_file)
        wfile_trimmed = os.path.join(self.working_dir, 'trimmed_{}'.format(self.working_file))

        # Record audio at given freq and duration using the arecord command
        rec_cmd = 'sudo arecord --device plughw:{},0 --channels {} --rate {} --format S16_LE --duration {} {}'
        call_cmd_line(rec_cmd.format(self.capture_card, self.channels, self.record_freq, self.record_length + self.rec_start_trim_secs, wfile))

        # Trim the first N seconds of audio to remove the 'popping' sound
        trim_cmd = 'ffmpeg -y -loglevel panic -i {} -ss {} {} >/dev/null 2>&1'
        call_cmd_line(trim_cmd.format(wfile, self.rec_start_trim_secs, wfile_trimmed))
        os.remove(wfile)

        # Move the recorded (and trimmed) file to a location where it will get compressed
        shutil.move(wfile_trimmed, os.path.join(self.working_dir, uncomp_f_name))

        logger.info('{} - Finished recording'.format(uncomp_f_name))

        return uncomp_f_name

    def postprocess(self, uncomp_f_name, cmd_on_complete=None):
        """
        Method to optionally compress raw audio data to mp3 format and stage data to
        upload folder
        """

        # current working file
        uncomp_path = os.path.join(self.working_dir, uncomp_f_name)

        if self.compress_data == True:
            # Compress the raw audio file to mp3 format
            comp_path = os.path.join(self.data_dir, uncomp_f_name) + '.mp3'
            logger.info('{} - Starting compression'.format(uncomp_f_name))
            cmd = ('ffmpeg -loglevel panic -i {} -codec:a libmp3lame -filter:a "volume={}" -qscale:a 0 -ac {} {} >/dev/null 2>&1') # VBR compression
            #cmd = ('ffmpeg -loglevel panic -i {} -codec:a libmp3lame -filter:a "volume=5" -b:a 192k -ac 1 {} >/dev/null 2>&1') # CBR compression
            call_cmd_line(cmd.format(uncomp_path, self.amplification, self.channels, comp_path))
            logger.info('{} - Finished audio compression'.format(uncomp_f_name))

        else:
            # Don't compress but still amplify the audio and store as WAV
            logger.info('{} - No compression of audio data, just amplification'.format(uncomp_f_name))
            out_path = os.path.join(self.data_dir, uncomp_f_name) + '.wav'
            cmd = ('ffmpeg -loglevel panic -i {} -filter:a "volume={}" {} >/dev/null 2>&1')
            call_cmd_line(cmd.format(uncomp_path, self.amplification, out_path))
            logger.info('{} - Finished audio amplification'.format(uncomp_f_name))

        # Remove the old working file
        if os.path.exists(uncomp_path):
            os.remove(uncomp_path)

        if cmd_on_complete:
            call_cmd_line(cmd_on_complete)
