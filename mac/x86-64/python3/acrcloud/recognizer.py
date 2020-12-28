#!/usr/bin/env python
#-*- coding:utf-8 -*-

'''
    @author qinxue.pan E-mail: xue@acrcloud.com
    @version 1.0.0
    @create 2015.10.01
'''

import os
import sys
import hmac
import time
import json
import base64
import hashlib
import urllib.request
import urllib.parse
import datetime

import acrcloud_extr_tool

'''
Copyright 2015 ACRCloud Recognizer v1.0.0

This module can recognize ACRCloud by most of audio/video file. 
        Audio: mp3, wav, m4a, flac, aac, amr, ape, ogg ...
        Video: mp4, mkv, wmv, flv, ts, avi ...

Example:
    config = {
        'host':'ap-southeast-1.api.acrcloud.com',
        'access_key':'XXXXXXXX',
        'access_secret':'XXXXXXXX',
        'timeout':5
    }
    re = ACRCloudRecognizer(config)

    #recognize by file path, and skip 180 seconds from from the beginning of "aa.mp3".
    print re.recognize_by_file('aa.mp3', 180)

    buf = open('aa.mp3', 'rb').read()
    #recognize by file_audio_buffer that read from file path, and skip 180 seconds from from the beginning of "aa.mp3".
    print re.recognize_by_filebuffer(buf, 180)

    #aa.wav is (RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 8000 Hz)
    buf = open('aa.wav', 'rb').read()
    buft = buf[1024000:192000+1024001]
    recognize by audio_buffer(RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 8000 Hz)
    print re.recognize(buft)
'''
class ACRCloudRecognizeType:
    ACR_OPT_REC_AUDIO = 0  # audio fingerprint
    ACR_OPT_REC_HUMMING = 1 # humming fingerprint
    ACR_OPT_REC_BOTH = 2 # audio and humming fingerprint
    ACR_OPT_REC_COVER = 3 # cover fingerprint

class ACRCloudRecognizer:
    def __init__(self, config):
        self.config = config
        self.host = config.get('host', 'ap-southeast-1.api.acrcloud.com')
        self.query_type = config.get('query_type', 'fingerprint')
        self.access_key = config.get('access_key')
        self.access_secret = config.get('access_secret')
        self.timeout = config.get('timeout', 5)
        self.recognize_type = config.get('recognize_type', ACRCloudRecognizeType.ACR_OPT_REC_AUDIO)
        if self.recognize_type > 2 or self.recognize_type < 0:
            self.recognize_type = ACRCloudRecognizeType.ACR_OPT_REC_AUDIO
        self.debug = config.get('debug', False)
        if not self.access_key or not self.access_secret:
            print('recognize init(none access_key or access_secret)')
            sys.exit(1)

        self.filter_energy_min = config.get('filter_energy_min', 0)
        self.silence_energy_threshold = config.get('silence_energy_threshold', 1200)
        self.silence_rate_threshold = config.get('silence_rate_threshold', 0.7)

        if self.debug:
            acrcloud_extr_tool.set_debug()

    def post_multipart(self, url, fields, files, timeout):
        content_type, body = self.encode_multipart_formdata(fields, files)
        
        if not content_type and not body:
            return ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.HTTP_ERROR_CODE, 'encode_multipart_formdata error')

        try:
            req = urllib.request.Request(url, data=body)
            req.add_header('Content-Type', content_type)
            req.add_header('Referer', url)
            resp = urllib.request.urlopen(req, timeout=timeout)
            ares = resp.read().decode('utf8')
            return ares
        except Exception as e:
            return ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.HTTP_ERROR_CODE, str(e))
        
    def encode_multipart_formdata(self, fields, files):
        try:
            boundary = "*****2016.05.27.acrcloud.rec.copyright." + str(time.time()) + "*****"
            body = b''
            CRLF = '\r\n'
            L = []
            for (key, value) in list(fields.items()):
                L.append('--' + boundary)
                L.append('Content-Disposition: form-data; name="%s"' % key)
                L.append('')
                L.append(value)

            body = bytes(CRLF.join(L), encoding='utf-8')

            for (key, value) in list(files.items()):
                L = []
                L.append(CRLF + '--' + boundary)
                L.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, key))
                L.append('Content-Type: application/octet-stream')
                L.append(CRLF)
                body = body + CRLF.join(L).encode('ascii') + value
            body = body + (CRLF + '--' + boundary + '--' + CRLF + CRLF).encode('ascii')
            content_type = 'multipart/form-data; boundary=%s' % boundary
            return content_type, body
        except Exception as e:
            print('encode_multipart_formdata error' + str(e))
        return None, None

    def do_recogize(self, host, query_data, query_type, access_key, access_secret, timeout=5, user_params={}):
        http_method = "POST"
        http_url_file = "/v1/identify"
        data_type = query_type
        signature_version = "1"
        timestamp = int(time.mktime(datetime.datetime.utcfromtimestamp(time.time()).timetuple()))
        sample_bytes = str(len(query_data))
        
        string_to_sign = http_method+"\n"+http_url_file+"\n"+access_key+"\n"+data_type+"\n"+signature_version+"\n"+str(timestamp)
        hmac_res = hmac.new(access_secret.encode('ascii'), string_to_sign.encode('ascii'), digestmod=hashlib.sha1).digest()
        sign = base64.b64encode(hmac_res).decode('ascii')
    
        fields = {'access_key':access_key, 
                  'sample_bytes':sample_bytes, 
                  'timestamp':str(timestamp), 
                  'signature':sign, 
                  'data_type':data_type, 
                  "signature_version":signature_version}
        for k,v in user_params.items():
            fields[k] = v

        sample_bytes = 0
        sample_hum_bytes = 0
        if 'sample' in query_data:
            if query_data['sample'] == None:
                return ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.DECODE_ERROR_CODE)
            sample_bytes = len(query_data['sample'])
            if sample_bytes == 0:
                return ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.MUTE_ERROR_CODE)
            fields['sample_bytes'] = str(sample_bytes)

        if 'sample_hum' in query_data:
            if query_data['sample_hum'] == None:
                return ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.DECODE_ERROR_CODE)
            sample_hum_bytes = len(query_data['sample_hum'])
            if sample_bytes == 0 and sample_hum_bytes == 0:
                return ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.NOT_HUMMING_ERROR_CODE)
            fields['sample_hum_bytes'] = str(sample_hum_bytes)

        server_url = 'https://' + host + http_url_file
        res = self.post_multipart(server_url, fields, query_data, timeout)
        return res

    def recognize(self, wav_audio_buffer, cfactor = 4):
        res = ''
        try:
            query_data = {}
            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_AUDIO or self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_BOTH:
                audio_fingerprint_opt = {
                    'filter_energy_min': self.filter_energy_min,
                    'silence_energy_threshold': self.silence_energy_threshold,
                    'silence_rate_threshold': self.silence_rate_threshold
                }
                query_data['sample'] = acrcloud_extr_tool.create_fingerprint(wav_audio_buffer, False, audio_fingerprint_opt)

            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_HUMMING or self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_BOTH:
                query_data['sample_hum'] = acrcloud_extr_tool.create_humming_fingerprint(wav_audio_buffer)

            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_COVER:
                query_data['sample'] = acrcloud_extr_tool.create_cs_fingerprint(wav_audio_buffer, 1, cfactor)

            res = self.do_recogize(self.host, query_data, self.query_type, self.access_key, self.access_secret, self.timeout)
            try:
                json.loads(res)
            except Exception as e:
                res = ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.JSON_ERROR_CODE, str(res))
        except Exception as e:
            res = ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.UNKNOW_ERROR_CODE, str(e))
        return res

    def recognize_audio(self, file_path, start_seconds=0, rec_length=10, user_params={}):
        res = ''
        try:
            query_data = {}
            query_data['sample'] = acrcloud_extr_tool.decode_audio_by_file(file_path, start_seconds, rec_length, 8000)
            if not query_data['sample'] or len(query_data['sample']) < 16000:
                return ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.AUDIO_ERROR_CODE)
            res = self.do_recogize(self.host, query_data, 'audio', self.access_key, self.access_secret, self.timeout, user_params)
        except Exception as e:
            res = ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.UNKNOW_ERROR_CODE, str(e))
        return res

    
    def recognize_by_file(self, file_path, start_seconds, rec_length=10, user_params={}, cfactor=4):
        res = ''
        try:
            query_data = {}
            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_AUDIO or self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_BOTH:
                audio_fingerprint_opt = {
                    'filter_energy_min': self.filter_energy_min,
                    'silence_energy_threshold': self.silence_energy_threshold,
                    'silence_rate_threshold': self.silence_rate_threshold
                }
                query_data['sample'] = acrcloud_extr_tool.create_fingerprint_by_file(file_path, start_seconds, rec_length, False, audio_fingerprint_opt)
            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_HUMMING or self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_BOTH:
                query_data['sample_hum'] = acrcloud_extr_tool.create_humming_fingerprint_by_file(file_path, start_seconds, rec_length)
            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_COVER:
                query_data['sample'] = acrcloud_extr_tool.create_cs_fingerprint_by_file(file_path, start_seconds, rec_length, 1, cfactor)

            res = self.do_recogize(self.host, query_data, self.query_type, self.access_key, self.access_secret, self.timeout, user_params)
            try:
                json.loads(res)
            except Exception as e:
                res = ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.JSON_ERROR_CODE, str(res))
        except Exception as e:
            res = ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.UNKNOW_ERROR_CODE, str(e))
        return res

    def recognize_by_filebuffer(self, file_buffer, start_seconds, rec_length=10, user_params={}, cfactor=4):
        res = ''
        try:
            query_data = {}
            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_AUDIO or self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_BOTH:
                audio_fingerprint_opt = {
                    'filter_energy_min': self.filter_energy_min,
                    'silence_energy_threshold': self.silence_energy_threshold,
                    'silence_rate_threshold': self.silence_rate_threshold
                }
                query_data['sample'] = acrcloud_extr_tool.create_fingerprint_by_filebuffer(file_buffer, start_seconds, rec_length, False, audio_fingerprint_opt)
            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_HUMMING or self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_BOTH:
                query_data['sample_hum'] = acrcloud_extr_tool.create_humming_fingerprint_by_filebuffer(file_buffer, start_seconds, rec_length)
            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_COVER:
                query_data['sample'] = acrcloud_extr_tool.create_cs_fingerprint_by_filebuffer(file_buffer, start_seconds, rec_length, 1, cfactor)

            res = self.do_recogize(self.host, query_data, self.query_type, self.access_key, self.access_secret, self.timeout, user_params)
            try:
                json.loads(res)
            except Exception as e:
                res = ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.JSON_ERROR_CODE, str(res))
        except Exception as e:
            res = ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.UNKNOW_ERROR_CODE, str(e))
        return res

    def recognize_by_fpbuffer(self, fp_buffer, start_seconds=0, rec_length=10):
        res = ''
        try:
            query_data = {}
            if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_AUDIO or self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_BOTH:
                query_data['sample'] = acrcloud_extr_tool.create_fingerprint_by_fpbuffer(fp_buffer, start_seconds, rec_length)
            #if self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_HUMMING or self.recognize_type == ACRCloudRecognizeType.ACR_OPT_REC_BOTH:
            #    query_data['sample_hum'] = acrcloud_extr_tool.create_humming_fingerprint_by_filebuffer(file_buffer, start_seconds, rec_length)

            res = self.do_recogize(self.host, query_data, self.query_type, self.access_key, self.access_secret, self.timeout)
            try:
                json.loads(res)
            except Exception as e:
                res = ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.JSON_ERROR_CODE, str(res))
        except Exception as e:
            res = ACRCloudStatusCode.get_result_error(ACRCloudStatusCode.UNKNOW_ERROR_CODE, str(e))
        return res

    @staticmethod
    def get_duration_ms_by_file(file_path):
        try:
            duration_ms = acrcloud_extr_tool.get_duration_ms_by_file(file_path)
            return duration_ms
        except Exception as e:
            return 0

    @staticmethod
    def get_duration_ms_by_fpbuffer(fp_buffer):
        try:
            duration_ms = acrcloud_extr_tool.get_duration_ms_by_fpbuffer(fp_buffer)
            return duration_ms
        except Exception as e:
            return 0


class ACRCloudStatusCode:
    HTTP_ERROR_CODE = 3000
    NO_RESULT_CODE = 1001
    DECODE_ERROR_CODE = 2004
    MUTE_ERROR_CODE = 2006
    AUDIO_ERROR_CODE = 2004
    NOT_HUMMING_ERROR_CODE = 2007
    UNKNOW_ERROR_CODE = 2010
    JSON_ERROR_CODE = 2002

    CODE_MSG = {
        HTTP_ERROR_CODE : 'Http Error', 
        NO_RESULT_CODE : 'No Result', 
        MUTE_ERROR_CODE: 'May Be Mute', 
        DECODE_ERROR_CODE : 'Decode Audio Error', 
        NOT_HUMMING_ERROR_CODE: 'May Be Not Humming', 
        UNKNOW_ERROR_CODE : 'Unknow Error',
        JSON_ERROR_CODE : 'Json Error'
    }

    @staticmethod
    def get_result_error(res_code, msg=''):
        if ACRCloudStatusCode.CODE_MSG.get(res_code) == None:
            return None
        res = {'status':{'msg':ACRCloudStatusCode.CODE_MSG[res_code], 'code':res_code}}
        if msg:
            res = {'status':{'msg':ACRCloudStatusCode.CODE_MSG[res_code]+':'+msg, 'code':res_code}}
        return json.dumps(res)


if __name__ == '__main__':
    config = {
        'host':'ap-southeast-1.api.acrcloud.com',
        'access_key':'XXXXXXXX',
        'access_secret':'XXXXXXXX',
        'timeout':5
    }

    
    re = ACRCloudRecognizer(config)
    buf = open(sys.argv[1], 'rb').read()
    #buft = buf[1024000:192000+1024001]

    acrcloud_extr_tool.set_debug()
    #print(acrcloud_extr_tool.__doc__)
    #print(re.recognize_by_file(sys.argv[1], 10))
    print(re.recognize_by_filebuffer(buf, 10))
    #print re.recognize(buft)
