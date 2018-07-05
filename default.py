#!/usr/bin/env python
# -*- coding: utf-8 -*-

## START: Copied from the original plugin by Štěpán Ort ##
import sys
import os
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib
import json
import random
from uuid import getnode as get_mac
## END: Copied from the original plugin by Štěpán Ort ##
import datetime
import time
import gzip
import re
import glob
import traceback
try:
    # Python 3
    from urllib.parse import urlparse, parse_qs
except ImportError:
    # Python 2
    from urlparse import urlparse, parse_qs
import xml.etree.ElementTree as etree

from o2tvgo import O2TVGO,  LiveChannel,  AuthenticationError, ChannelIsNotBroadcastingError,  TooManyDevicesError
from logs import Logs
from jsonrpc import JsonRPC
from db import O2tvgoDB

reload(sys)
sys.setdefaultencoding('utf-8')

params = False

try:
    ###############################################################################
    ## Globals ##
    _addon_ = xbmcaddon.Addon('plugin.video.o2tvgo.iptv.simple')
    _scriptname_ = _addon_.getAddonInfo('name')
    _logs_ = Logs(_scriptname_)
    _jsonRPC_ = JsonRPC(_logs_)
    _addon_pvrIptvSimple_ = None
    _useIptvSimpleTimeshift_ = True
    _epgTimeshift_ = 0

    def _isAddonInstalled(addonId):
        addons = _jsonRPC_._getAddons()
        if addons:
            for addon in addons:
                if addonId == addon["addonid"]:
                    return True
            return False
        else:
            # No/incorrect response from jsonrpc server
            return False

    def _getPvrIptvSimpleEpgShift(default):
        global _addon_pvrIptvSimple_
        shift = None
        if not _addon_pvrIptvSimple_:
            pluginDetails = _jsonRPC_._getAddonDetails("pvr.iptvsimple")
            if pluginDetails:
                #logNtc("Response: "+_toString(pluginDetails))
                enabled = pluginDetails["enabled"]
                if enabled:
                    _addon_pvrIptvSimple_ = xbmcaddon.Addon('pvr.iptvsimple')
                else:
                    response = _jsonRPC_._setAddonEnabled("pvr.iptvsimple", True)
                    if response:
                        xbmc.sleep(1000)
                        _addon_pvrIptvSimple_ = xbmcaddon.Addon('pvr.iptvsimple')
        if _addon_pvrIptvSimple_:
            shift = _addon_pvrIptvSimple_.getSetting("epgTimeShift")
        if not shift:
            msg = _lang_(30250) % default
            notificationWarning(msg)
            logErr(msg)
            shift = default
        return float(shift)

    ## START: Copied from the original plugin by Štěpán Ort ##
    def _deviceId():
        mac = get_mac()
        hexed = hex((mac*7919)%(2**64))
        return ('0000000000000000'+hexed[2:-1])[16:]

    def _randomHex16():
        return ''.join([random.choice('0123456789abcdef') for x in range(16)])

    ## START changes by @ch ##

    ## First run ##
    if not (_addon_.getSetting("settings_init_done") == 'true'):
        O2TVGO_SETTING_KEYS = ['username',  'password',  'send_errors', 'device_id']
        o2tvGoAddonId = "plugin.video.o2tvgo"
        isO2TVGoInstalled = _isAddonInstalled(o2tvGoAddonId)
        if isO2TVGoInstalled:
            o2tvGoPluginDetails = _jsonRPC_._getAddonDetails(o2tvGoAddonId)
            if o2tvGoPluginDetails and "enabled" in o2tvGoPluginDetails:
                isO2TVGoEnabled = o2tvGoPluginDetails["enabled"]
                if isO2TVGoEnabled:
                    _logs_.logNtc("Setting values from O2TV Go plugin")
                    _addon_o2tvgo_ = xbmcaddon.Addon(o2tvGoAddonId)
                    for settingKey in O2TVGO_SETTING_KEYS:
                        settingVal = _addon_o2tvgo_.getSetting(settingKey)
                        if settingVal:
                            _addon_.setSetting(settingKey, settingVal)
        _logs_.logNtc("Setting default values")
        DEFAULT_SETTING_VALUES = {
            'send_errors' : 'false', 
            'use_iptv_simple_timeshift': 'true', 
            'epg_timeshift' : str(_getPvrIptvSimpleEpgShift(0)),
            'channel_refresh_rate': '3', 
            'epg_refresh_rate': '12', 
            'limit_epg_per_batch': 'true', 
            'epg_fetch_batch_limit': '10', 
            'epg_fetch_batch_timeout': '10', 
            'force_restart': 'false', 
            'use_additional_m3u': '0', 
            'use_additional_epg': '0', 
            'configure_cron': 'false',
            'notification_disable_all': 'false', 
            'notification_refreshing_started': 'true', 
            'notification_pvr_restart': 'true', 
        }
        for setting in DEFAULT_SETTING_VALUES.keys():
            val = _addon_.getSetting(setting)
            if not val:
                _addon_.setSetting(setting, DEFAULT_SETTING_VALUES[setting])
        _addon_.setSetting("settings_init_done", "true")
    
    ## Get / set timeshift ##
    _useIptvSimpleTimeshift_ = (_addon_.getSetting('use_iptv_simple_timeshift') == 'true')
    if _useIptvSimpleTimeshift_:
        _epgTimeshift_ = _getPvrIptvSimpleEpgShift(0)
        timeshiftLoc = _addon_.getSetting('epg_timeshift')
        if float(timeshiftLoc) != _epgTimeshift_:
            _addon_.setSetting("epg_timeshift", str(_epgTimeshift_))
    else:
        _epgTimeshift_ = _addon_.getSetting('epg_timeshift')
        if _epgTimeshift_:
            _epgTimeshift_ = float(_epgTimeshift_)

    ## Get refresh rates and limits and other settings as global vars ##
    _epg_refresh_rate_ = (int(_addon_.getSetting('epg_refresh_rate')) * 60 * 60) - (10 * 60)
    _limit_epg_per_batch_ = (_addon_.getSetting('limit_epg_per_batch') == 'true')
    _epg_fetch_batch_limit_ = 999999
    _epgLockTimeout_ = 0
    if _limit_epg_per_batch_:
        _epg_fetch_batch_limit_ = int(_addon_.getSetting('epg_fetch_batch_limit'))
        _epgLockTimeout_ = (int(_addon_.getSetting('epg_fetch_batch_timeout')) * 60)
    _channel_refresh_rate_ = (int(_addon_.getSetting('channel_refresh_rate')) * 60 * 60) - (10 * 60)
    _force_restart_ = (_addon_.getSetting('force_restart') == 'true')
    _use_additional_m3u_ = not (_addon_.getSetting('use_additional_m3u') == '0')
    if _use_additional_m3u_:
        # TODO: 1 - file, 2 - folder, 3 - pattern
        _m3u_additional_ = xbmc.translatePath('special://home/o2tvgo-prgs-additional.m3u')
    _use_additional_epg_ = not (_addon_.getSetting('use_additional_epg') == '0')
    if _use_additional_epg_:
        # TODO: 1 - file, 2 - folder, 3 - pattern
        _xmltv_additional_filelist_pattern_ = xbmc.translatePath('special://home/rytecxmltv*.gz')
        _xmltv_additional_ = xbmc.translatePath('special://home/merged_epg.xml')
        _xmltv_additional_gzip_ = xbmc.translatePath('special://home/merged_epg.xml.gz')
        _xmltv_test_output_file_ = xbmc.translatePath('special://home/merged_xml_test_out.xml')
    _configure_cron_ = (_addon_.getSetting('configure_cron') == 'true')
    _notification_disable_all_ = (_addon_.getSetting('notification_disable_all') == 'true')
    _notification_refreshing_started_ = (_addon_.getSetting('notification_refreshing_started') == 'true')
    _notification_pvr_restart_ = (_addon_.getSetting('notification_pvr_restart') == 'true')
    _logFilePath_ = xbmc.translatePath('special://logpath/kodi.log')

    ## END changes by @ch ##

    _device_id_ = _addon_.getSetting("device_id")
    if not _device_id_:
        first_device_id = _deviceId()
        second_device_id = _deviceId()
        if first_device_id == second_device_id:
            _device_id_ = first_device_id
        else:
            _device_id_ = _randomHex16()
            ## START changes by @ch ##
#            if _device_name_:
#                _device_id_ = _fromDeviceId()
#            else:
#                _device_id_ = _randomHex16()
            ## END changes by @ch ##
        _addon_.setSetting("device_id", _device_id_)

    ###############################################################################
    _profile_ = xbmc.translatePath(_addon_.getAddonInfo('profile')).decode("utf-8")
    _lang_   = _addon_.getLocalizedString
#    _first_error_ = (_addon_.getSetting('first_error') == "true")
    _send_errors_ = (_addon_.getSetting('send_errors') == "true")
    _version_ = _addon_.getAddonInfo('version')
    _username_ = _addon_.getSetting("username")
    _password_ = _addon_.getSetting("password")
    _format_ = 'video/' + _addon_.getSetting('format').lower()
    _icon_ = xbmc.translatePath( os.path.join(_addon_.getAddonInfo('path'), 'icon.png' ) )
    _handle_ = int(sys.argv[1])
    _baseurl_ = sys.argv[0]

    _o2tvgo_ = O2TVGO(_device_id_, _username_, _password_, _logs_, _scriptname_)
    
    _db_path_ = _profile_+'o2tvgo.db'
    _addon_path_ = _addon_.getAddonInfo('path')+"/"
    _db_ = O2tvgoDB(_db_path_, _profile_, _addon_path_, _notification_disable_all_, _logs_)
    
    _db_.setLock("timeshift", _epgTimeshift_)

    ###############################################################################
    def _fetchChannels():
        global _o2tvgo_
        channels = None
        ex = False
        while not channels:
            try:
                channels = _o2tvgo_.live_channels()
            except AuthenticationError:
                if ex:
                    return None
                ex = True
                d = xbmcgui.Dialog()
                d.notification(_scriptname_, _lang_(30003), xbmcgui.NOTIFICATION_ERROR)
                _reload_settings()
            except TooManyDevicesError:
                d = xbmcgui.Dialog()
                d.notification(_scriptname_, _lang_(30006), xbmcgui.NOTIFICATION_ERROR)
                return None
        return channels

    def _reload_settings():
        _addon_.openSettings()
#        global _first_error_
#        _first_error_ = (_addon_.getSetting('first_error') == "true")
        global _send_errors_
        _send_errors_ = (_addon_.getSetting('send_errors') == "true")
        global _username_
        _username_ = _addon_.getSetting("username")
        global _password_
        _password_ = _addon_.getSetting("password")
        global _o2tvgo_
        _o2tvgo_ = O2TVGO(_device_id_, _username_, _password_, _logs_, _scriptname_)


    ## END: Copied from the original plugin by Štěpán Ort ##

    ###############################################################################
    ## Logging, debugging, messages - just redeclaring the methods from Logging so I don't have to rewrite every occurence
    def _toString(text):
        return _logs_._toString(text)
    def log(msg, level=xbmc.LOGDEBUG):
        return _logs_.log(msg,  level)
    def logDbg(msg):
        return _logs_.logDbg(msg)
    def logNtc(msg):
        return _logs_.logNtc(msg)
    def logWarn(msg):
        return _logs_.logWarn(msg)
    def logErr(msg):
        return _logs_.logErr(msg)
    def notificationInfo(msg, sound = False,  force = False, dialog = True):
        logNtc(msg)
        if (dialog and not _notification_disable_all_) or force:
            return _logs_.notificationInfo(msg,  sound)
    def notificationWarning(msg, sound = True,  force = False, dialog = True):
        logWarn(msg)
        if (dialog and not _notification_disable_all_) or force:
            return _logs_.notificationWarning(msg,  sound)
    def notificationError(msg, sound = True,  force = False, dialog = True):
        logErr(msg)
        if (dialog and not _notification_disable_all_) or force:
            return _logs_.notificationError(msg,  sound)

    ###############################################################################
    ## Globals ##
    _xmltv_ = xbmc.translatePath('special://home/o2tvgo-epg.xml')
    _m3u_ = xbmc.translatePath('special://home/o2tvgo-prgs.m3u')
    # DEPRECATED BEGIN #
    _xmltv_json_base_ = _profile_+'o2tvgo-epg-'
    _m3u_json_ = _profile_+'o2tvgo-prgs.json'
    _next_programme_ = _profile_+'o2tvgo-next_programme.json'
    _restart_ok_ = _profile_+'o2tvgo-restart_ok.txt'
    _save_epg_lock_file_ = _profile_+'o2tvgo-save_epg.lock'
    # DEPRECATED END #

    ###############################################################################
    def _emptyFunction():
        logDbg("function was replaced with a dummy empty one")

    def upgradeConfigsFromJsonToDb():
        silentAdd = True
        if os.path.exists(_m3u_json_):
            try:
                successM3U = False
                with open(_m3u_json_) as data_file:
                    channelsDict = json.load(data_file)
                if channelsDict and "list" in channelsDict:
                    channelListDict = channelsDict["list"]
                    indexesByBaseNames = channelsDict["indexesByBaseNames"]
                    baseNamesByIndexes = {}
                    for baseName in indexesByBaseNames:
                        i = indexesByBaseNames[baseName]
                        baseNamesByIndexes[i] = baseName
                    indexesByKey = channelsDict["indexesByKey"]
                    successM3U = True
                    for k in channelListDict:
                        ch = channelListDict[k]
                        channelKeyClean = re.sub(r"[^a-zA-Z0-9_]", "_", ch["channel_key"])
                        id = _db_.getChannelID(keyOld=ch["channel_key"], keyCleanOld=channelKeyClean, silent=silentAdd)
                        if not id:
                            index = indexesByKey[ch["channel_key"]]
                            baseName = baseNamesByIndexes[index]
                            idNew = _db_.addChannel(ch["channel_key"],  channelKeyClean,  ch["name"], baseName)
                            if not idNew:
                                successM3U = False
                if channelsDict and "chJsNumByIndex" in channelsDict:
                    for i in channelsDict["chJsNumByIndex"]:
                        channelKey = channelsDict["keysByIndex"][i]
                        channelKeyClean = re.sub(r"[^a-zA-Z0-9_]", "_", channelKey)
                        channelID = _db_.getChannelID(keyOld=channelKey, keyCleanOld=channelKeyClean)
                        successEpg = True
                        jsonEpgFile = None
                        if channelID:
                            channelJsonNumber = channelsDict["chJsNumByIndex"][i]
                            jsonEpgFilePath = _xmltv_json_base_ + str(channelJsonNumber) + ".json"
                            jsonEpgFile = xbmc.translatePath(jsonEpgFilePath)
                            if os.path.exists(jsonEpgFile):
                                successEpg = False
                                with open(jsonEpgFile) as data_file:
                                    epg = json.load(data_file)
                                    successEpg = True
                                    for key in sorted(epg.iterkeys()):
                                        oneEpg = epg[key]
                                        idEpg, channelIDFound = _db_.getEpgID(epgIdOld=oneEpg["epgId"], startOld=oneEpg["start"], channelID=channelID, silent=silentAdd)
                                        if not idEpg:
                                            idNew = _db_.addEpg(
                                                epgId = oneEpg["epgId"],
                                                start = oneEpg["start"],
                                                startTimestamp = oneEpg["startTimestamp"],
                                                startEpgTime = oneEpg["startEpgTime"],
                                                end = oneEpg["end"],
                                                endTimestamp = oneEpg["endTimestamp"],
                                                endEpgTime = oneEpg["endEpgTime"],
                                                title = oneEpg["title"],
                                                plot = oneEpg["plot"],
                                                plotoutline = oneEpg["plotoutline"],
                                                fanart_image = oneEpg["fanart_image"],
                                                genre = oneEpg["genre"],
                                                genres = json.dumps(oneEpg["genres"]), 
                                                channelID=channelID)
                                            if idNew:
                                                logNtc("Successfully imported EPG #"+str(oneEpg["epgId"])+" with new ID #"+str(idNew)+" from JSON file into DB.")
                                            else:
                                                successEpg = False
                                                successM3U = False
                                    if successEpg:
                                        logNtc("Successfully imported all EPG of channel #"+str(channelID)+" from JSON file into DB.")
                                        if jsonEpgFile:
                                            logNtc("Removing JSON file: "+jsonEpgFile)
                                            os.remove(jsonEpgFile)

                if successM3U:
                    logNtc("Successfully imported all JSON channels into DB. Removing JSON file: "+_m3u_json_)
                    os.remove(_m3u_json_)
                
            except Exception as e:
#                exc_type, exc_value, exc_traceback = sys.exc_info()
#                traceback.print_tb(exc_traceback, file=sys.stdout)
                logWarn("Exception while reading channels from json: "+str(e))
                return False
        if os.path.exists(_restart_ok_):
            lastRestartOK = os.path.getmtime(_restart_ok_)
            _db_.setLock("lastRestart", lastRestartOK)
            os.remove(_restart_ok_)
        
        if os.path.exists(_save_epg_lock_file_):
            fMtime = os.path.getmtime(_save_epg_lock_file_)
            _db_.setLock("saveEpgRunning", fMtime)
            os.remove(_save_epg_lock_file_)
        return True
    
    def _openIptvSimpleClientSettings():
        pluginDetails = _jsonRPC_._getAddonDetails("pvr.iptvsimple")
        if pluginDetails:
            enabled = pluginDetails["enabled"]
            if enabled:
                addon = xbmcaddon.Addon('pvr.iptvsimple')
                addon.openSettings()

    def _fetchEpg(channel_key, hoursToLoad = 24, hoursToLoadFrom = None, forceFromTimestamp = None):
        global _o2tvgo_
        _o2tvgo_.channel_key = channel_key
        _o2tvgo_.hoursToLoad = hoursToLoad
        if forceFromTimestamp:
            _o2tvgo_.forceFromTimestamp = forceFromTimestamp
        elif hoursToLoadFrom:
            _o2tvgo_.hoursToLoadFrom = hoursToLoadFrom
        epg_list = _o2tvgo_.channel_epg()
        return epg_list

    def _fetchEpgDetail(epg_id):
        global _o2tvgo_
        _o2tvgo_.epg_id = epg_id
        epg_detail = _o2tvgo_.epg_detail()
        return epg_detail

        player = xbmc.Player()
        isPlaying = player.isPlayingVideo()
        if not isPlaying:
            return None, None
        playingNow = player.getPlayingFile()
        if not playingNow:
            return None, None
        aPlayingNow = playingNow.split('/')
        playingNowFileName = aPlayingNow[-1]
        logDbg(playingNowFileName)
        return playingNow, playingNowFileName

#    def compareChannelHosts(ch1, ch2):
#        aCh1 = ch1.split('/')
#        aCh2 = ch2.split('/')
#        return aCh1[3] == aCh2[3]

    def dirListing():
        # This will give options to start saveEPG etc.
        addDirectoryItem("Show logs", _baseurl_+"?showlogs=1", image=_icon_, isFolder=False)
        addDirectoryItem("Refresh channels and/or EPG", _baseurl_+"?saveepg=1&forcenotifications=1", image=_icon_, isFolder=False)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False)

    def addDirectoryItem(label, url, plot=None, title=None, date=None, icon=_icon_, image=None, fanart=None, isFolder=True):
        li = xbmcgui.ListItem(label)
        if not title:
            title = label
        liVideo = {'title': title}
        if image:
            li.setThumbnailImage(image)
        li.setIconImage(icon)
        li.setInfo("video", liVideo)
        xbmcplugin.addDirectoryItem(handle=_handle_, url=url, listitem=li, isFolder=isFolder)

    def showLogs():
        if os.path.exists(_logFilePath_):
            logFile = open(_logFilePath_, 'r')
            if logFile:
                contentLines = []
#                search = "["+_scriptname_+"]"
                search = _scriptname_
                isPreviousLineOurs = False
                for logEntry in logFile:
                    if search in logEntry:
                        if "showlogs=1" in logEntry:
                            continue
                        line = re.sub(r"T\:\d+\s*", "", logEntry).replace(_scriptname_, "_O2TVGo_")
                        contentLines.append(line)
                        isPreviousLineOurs = True
                    elif "Previous line repeats" in logEntry and isPreviousLineOurs:
                        line = re.sub(r"T\:\d+\s*", "", logEntry)
                        contentLines.append(line)
                        isPreviousLineOurs = False
                    else:
                        isPreviousLineOurs = False
                logFile.close()
                
                if contentLines:
                    content = ""
                    for logEntry in reversed(contentLines):
                        content += logEntry + "\n"
                else:
                    notificationInfo(_lang_(30271) % _logFilePath_)
                    return True
            else:
                notificationError(_lang_(30508) % _logFilePath_)
                return False
        else:
            notificationError(_lang_(30512) % _logFilePath_)
            return False
        xbmcgui.Dialog().textviewer(_scriptname_+" | Logs", content)
        return True

    def _maybeRestartPVR(refreshRate):
        lastRestart = _db_.getLock("lastRestart")
        if lastRestart > 0:
            timestampNow = int(time.time())
            if (timestampNow - lastRestart) >= (refreshRate):
                _restartPVR()
        else:
            _restartPVR()

    def _is_saveEpg_running():
        locktime = _db_.getLock("saveEpgRunning")
        timestampNow = int(time.time())
        if (timestampNow - locktime) >= (_epgLockTimeout_):
            return False
        else:
            return True

    def _setSaveEpgLock():
        _db_.setLock("saveEpgRunning", time.time())
 
    def saveChannels(restartPVR = True,  forceNotifications = False):
#        if not forceNotifications:
#            return False
        notification = _notification_refreshing_started_ or forceNotifications
        dialogDebug = False or forceNotifications
        
        msg = _lang_(30262) % "saveChannels()"
        notificationInfo(msg,  False,  forceNotifications,  dialogDebug)
        
        if os.path.exists(_m3u_):
            lastModTimeM3U = os.path.getmtime(_m3u_)
            timestampNow = int(time.time())
            if _use_additional_m3u_ and os.path.exists(_m3u_additional_):
                lastModTimeM3UAdditional = os.path.getmtime(_m3u_additional_)
                if (timestampNow - lastModTimeM3U) <= (_channel_refresh_rate_) and (lastModTimeM3U - lastModTimeM3UAdditional) >= 0:
                    msg = _lang_(30263) % (_m3u_,  _m3u_additional_)
                    notificationInfo(msg,  False,  forceNotifications,  dialogDebug)
                    _maybeRestartPVR(_channel_refresh_rate_)
                    return True
            elif (timestampNow - lastModTimeM3U) < (_channel_refresh_rate_):
                msg = _lang_(30264) % _m3u_
                notificationInfo(msg,  False,  forceNotifications,  dialogDebug)
                _maybeRestartPVR(_channel_refresh_rate_)
                return True
        msg = _lang_(30265)
        notificationInfo(msg,  False,  forceNotifications,  dialogDebug)
        channels = _fetchChannels()
        if not channels:
            msg = _lang_(30507)
            notificationError(msg,  True,  forceNotifications,  dialogDebug)
            return False
        notificationInfo(_lang_(30251),  False,  forceNotifications,  notification)
        
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        numberOfChannels = len(channels_sorted)
        iChannelJsonNumber = 0
        m3uLines = []
        m3uLines.append("#EXTM3U")
        for channel in channels_sorted:
            try:
#                logDbg("Processing channel "+channel.name+" ("+str(iChannelJsonNumber+1)+"/"+str(numberOfChannels)+")")
                channelName = _toString(channel.name)
                channelKey = _toString(channel.channel_key)
                line = '#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="O2TVGO", %s' % (channelKey, channelName, _toString(channel.logo_url), channelName)
                m3uLines.append(line)

                channel_url = _toString(channel.url())
                m3uLines.append(channel_url)

                aUrl = channel_url.split('/')
                sUrlFileName = aUrl[-1]
                aUrlFileName = sUrlFileName.split('.')
                channelUrlBaseName = aUrlFileName[0]
                channelKeyClean = re.sub(r"[^a-zA-Z0-9_]", "_", channelKey)
                
                _db_.updateChannel(key=channelKey, keyClean=channelKeyClean, name=channelName, baseName=channelUrlBaseName,  id=None, keyOld=channelKey, keyCleanOld=channelKeyClean, nameOld=None)

                iChannelJsonNumber += 1
            except ChannelIsNotBroadcastingError:
                logDbg("Channel "+channel.name+" ("+str(iChannelJsonNumber+1)+"/"+str(numberOfChannels)+") is not broadcasting; skipping it")
                iChannelJsonNumber += 1 # Otherwise the EPG guides get mixed up!

        m3u = "\n".join(m3uLines)
#        logDbg("After joining lines")
        
#        logNtc("DEVEL STOP")
#        return False

        if _use_additional_m3u_ and os.path.exists(_m3u_additional_):
            additional_m3u = open(_m3u_additional_, 'r')
            if additional_m3u:
                additional_prgs = additional_m3u.read()
                additional_m3u.close()
                if additional_prgs:
                    m3u += additional_prgs
            else:
                msg = _lang_(30508) % _m3u_additional_
                notificationError(msg,  True,  forceNotifications,  dialogDebug)
                return False
        m3u_file = open(_m3u_, 'w+')
        if m3u_file:
            m3u_file.write(m3u)
            m3u_file.close()
            msg = _lang_(30266) % _m3u_
            notificationInfo(msg,  False,  forceNotifications,  dialogDebug)
            if restartPVR:
                _restartPVR()
        else:
            msg = _lang_(30509) % _m3u_
            notificationError(msg,  True,  forceNotifications,  dialogDebug)
            return False
        return True

    def _getChannelsListDict():
        channelsDict = _db_.getChannels()
        if channelsDict:
            return channelsDict
        else:
            channelsDict = {}
        i = 0
        logNtc("Fetching channels")
        channels = _fetchChannels()
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        for channel in channels_sorted:
            channelKeyClean = re.sub(r"[^a-zA-Z0-9_]", "_", channel.channel_key)
            _db_.updateChannel(key=channel.channel_key, keyClean=None, name=channel.name, baseName=None,  id=None, keyOld=channel.channel_key, keyCleanOld=channelKeyClean, nameOld=None)
            channelsDict[i] = {
               "id": 0, 
                "name": channel.name,
                "channel_key": channel.channel_key, 
                "epgLastModTimestamp": 0
            }
            i += 1
        logNtc("Saved channel list")
        return channelsDict

    def saveEPG(restartPVR = False,  forceNotifications = False):
        notification = _notification_refreshing_started_ or forceNotifications
        dialogDebug = False or forceNotifications
        
        msg = _lang_(30262) % "saveEPG()"
        notificationInfo(msg,  False,  forceNotifications,  dialogDebug)

        if _is_saveEpg_running():
            msg = _lang_(30257) % "saveEPG()"
            notificationInfo(msg,  False,  forceNotifications,  dialogDebug)
            _maybeRestartPVR(_epg_refresh_rate_)
            return True

        if os.path.exists(_xmltv_):
            lastModTimeXML = os.path.getmtime(_xmltv_)
            timestampNow = int(time.time())
            if _use_additional_m3u_ and os.path.exists(_m3u_additional_):
                lastModTimeM3UAdditional = os.path.getmtime(_m3u_additional_)
                if (timestampNow - lastModTimeXML) <= (_epg_refresh_rate_) and (lastModTimeXML - lastModTimeM3UAdditional) >= 0:
                    msg = _lang_(30263) % (_xmltv_,  _m3u_additional_)
                    notificationInfo(msg,  False,  forceNotifications,  dialogDebug)
                    _maybeRestartPVR(_epg_refresh_rate_)
                    return True
            elif (timestampNow - lastModTimeXML) <= (_epg_refresh_rate_):
                msg = _lang_(30264) % _xmltv_
                notificationInfo(msg,  False,  forceNotifications,  dialogDebug)
                _maybeRestartPVR(_epg_refresh_rate_)
                return True
        
        msg = _lang_(30258)
        notificationInfo(msg,  False,  forceNotifications,  dialogDebug)
        
        channelsDict = _getChannelsListDict()
        if not channelsDict:
            msg = _lang_(30510)
            notificationError(msg,  True,  forceNotifications,  dialogDebug)
            return False
        #logNtc(_toString(channelsDict))
        _setSaveEpgLock()
        
        notificationInfo(_lang_(30252),  False,  forceNotifications,  notification)
        
        numberOfChannels = len(channelsDict)
        i = 0
        et_tv = etree.Element("tv")
        while i < numberOfChannels or str(i) in channelsDict:
            key = str(i)
            if not key in channelsDict:
                i += 1
                numberOfChannels += 1
                continue
            channel = channelsDict[key]
            et_channel = etree.SubElement(et_tv, "channel", id=channel["channel_key"])
            etree.SubElement(et_channel, "display-name", lang="sk").text = channel["name"]
            i += 1
        _setSaveEpgLock()

        iFetchedChannel = 0
        i = 0
        errorOccured = False
        while i < numberOfChannels or str(i) in channelsDict:
            key = str(i)
            if not key in channelsDict:
                logDbg("No channel at position "+str(i+1)+"/"+str(numberOfChannels)+"; skipping it")
                i += 1
                continue
            channel = channelsDict[key]
            # read the db and delete old entries #
            epgDict = None
            useFromTimestamp = False
            useDB = False
            timestampNow = int(time.time())
            
            if (timestampNow - channel["epgLastModTimestamp"]) <= _epg_refresh_rate_:
                # use this instead of asking for the data #
                useDB = True
                #logNtc(channel["name"]+" 1")
            olderThan = (timestampNow -  (2*24*3600))
            _db_.deleteOldEpg(endBefore = olderThan)
            epgDict = _db_.getEpgRows(channel["id"])
            if not epgDict:
                # if there were no epg entries with for this channel, so just use an empty dictionary #
                epgDict = {}
                useDB = False
                #logNtc(channel["name"]+" 2")
            else:
                # check if the latest programme in the epg starts in the future #
                maxTimestamp = max(epgDict, key=int)
                if (int(maxTimestamp) - int(timestampNow)) < _epg_refresh_rate_:
                    # Data is not fresh enough, we need to load new data - enough to do so from the maxTimestamp #
                    useDB = False
                    useFromTimestamp = True
                    #logNtc(channel["name"]+" 3")
                    #logNtc("Age of latest programme in seconds: "+str(int(maxTimestamp) - int(timestampNow)))
                    #logNtc("Latest programme: "+str(maxTimestamp)+" => "+_toString(epgDict[maxTimestamp]))
            _setSaveEpgLock()

            if useDB:
                msg = _lang_(30259) % (channel["name"], i+1, numberOfChannels)
                notificationInfo(msg, False, forceNotifications, dialogDebug)
            else:
                if iFetchedChannel >= _epg_fetch_batch_limit_:
                    msg = _lang_(30267) % _epg_fetch_batch_limit_
                    notificationInfo(msg, False, forceNotifications, dialogDebug)
                    return True
                msg = _lang_(30268) % (channel["name"], i+1, numberOfChannels)
                notificationInfo(msg, False, forceNotifications, dialogDebug)
#                logNtc("DEVEL STOP")
#                return False
                forceFromTimestamp = None
                if useFromTimestamp:
                    forceFromTimestamp = maxTimestamp
                epg = _fetchEpg(channel["channel_key"], 2 * 24, 2 * 24, forceFromTimestamp)
                if epg:
                    for prg in epg:
                        epg_id = prg['epgId']
                        prg_detail = _fetchEpgDetail(epg_id)
                        if prg_detail['picture']:
                            fanart_image = "http://app.o2tv.cz" + prg_detail['picture']
                        elif prg['picture']:
                            fanart_image = "http://app.o2tv.cz" + prg['picture']
                        else:
                            fanart_image = ""
                        genres = None
                        genre = None
                        if prg_detail['genres']:
                            genres = prg_detail['genres']
                            genre = "/".join(genres).replace('/', ' / ')
                            genres = json.dumps(genres), 
                        start = _timestampishToTimestamp(prg['startTimestamp'])
                        epgDict[start] = {
                                "start": start,
                                "end": _timestampishToTimestamp(prg['endTimestamp']),
                                "startEpgTime": _timestampishToEpgTime(prg['startTimestamp']),
                                "endEpgTime": _timestampishToEpgTime(prg['endTimestamp']),
                                "startTimestamp": prg['startTimestamp'],
                                "endTimestamp": prg['endTimestamp'],
                                "epgId": prg["epgId"],
                                "title": prg['name'],
                                "fanart_image": fanart_image,
                                "plotoutline": prg['shortDescription'],
                                "plot": prg_detail['longDescription'],
                                "genres": genres,
                                "genre": genre
                        }
                        _db_.updateEpg(
                                start = start,
                                end = _timestampishToTimestamp(prg['endTimestamp']),
                                startEpgTime = _timestampishToEpgTime(prg['startTimestamp']),
                                endEpgTime = _timestampishToEpgTime(prg['endTimestamp']),
                                startTimestamp = prg['startTimestamp'],
                                endTimestamp = prg['endTimestamp'],
                                epgId = prg['epgId'],
                                title = prg['name'],
                                fanart_image = fanart_image,
                                plotoutline = prg['shortDescription'],
                                plot = prg_detail['longDescription'],
                                genres = genres,
                                genre = genre, 
                                channelID = channel["id"], 
                                startOld = start, 
                                epgIdOld = prg['epgId']
                        )
                        # TODO: check if channel was updated #
                        _db_.updateChannel(channelID = channel["id"],  epgLastModTimestamp = int(time.time()))
                        _setSaveEpgLock()
                else:
                    msg = _lang_(30511) % _toString(epg)
                    notificationError(msg, True, forceNotifications, dialogDebug)
                    errorOccured = True
                iFetchedChannel += 1
                #logNtc("DEVEL STOP")
                #return False

            _setSaveEpgLock()

            # building the actual xml file #
            for epgDictKey in sorted(epgDict.iterkeys()):
                prg = epgDict[epgDictKey]
                et_programme = etree.SubElement(et_tv, "programme", channel=channel["channel_key"])
                if "startEpgTime" in prg:
                    et_programme.set("start", prg['startEpgTime'])
                    et_programme.set("stop", prg['endEpgTime'])
                else:
                    et_programme.set("start", _timestampishToEpgTime(prg['startTimestamp']))
                    et_programme.set("stop", _timestampishToEpgTime(prg['endTimestamp']))
                etree.SubElement(et_programme, "title", lang="sk").text = prg['title']
                etree.SubElement(et_programme, "sub-title", lang="sk").text = prg['plotoutline']
                etree.SubElement(et_programme, "desc", lang="sk").text = prg['plot']
                if "fanart_image" in prg and prg["fanart_image"]:
                    et_programme_icon = etree.SubElement(et_programme, "icon")
                    et_programme_icon.set("src", prg["fanart_image"])
                if "genre" in prg and prg["genre"]:
                    etree.SubElement(et_programme, "category", lang="sk").text = prg["genre"]
                _setSaveEpgLock()
            i += 1
        ## END: while
        
        if errorOccured:
            return False
        
#        xmlElTree = etree.ElementTree(et_tv)
        xmlString = etree.tostring(et_tv, encoding='utf8')
        xmltv_file = open(_xmltv_, 'w+')
        if xmltv_file:
            xmltv_file.write(xmlString)
            xmltv_file.close()
            msg = _lang_(30269) % _xmltv_
            notificationInfo(msg, False, forceNotifications, dialogDebug)
            if restartPVR:
                _restartPVR()
        _setSaveEpgLock()
        if not _use_additional_epg_:
            return True
        needToRestart = False
        et_tv, needToRestart = _merge_additional_epg_xml(et_tv)
        if needToRestart:
#            xmlElTree = etree.ElementTree(et_tv)
            xmlString = etree.tostring(et_tv, encoding='utf8')
            xmltv_file = open(_xmltv_, 'w+')
            if xmltv_file:
                xmltv_file.write(xmlString)
                xmltv_file.close()
                msg = _lang_(30270) % _xmltv_
                notificationInfo(msg, False, forceNotifications, dialogDebug)
                if restartPVR:
                    _restartPVR()
            _setSaveEpgLock()
        return True

    def _restartPVR():
        _db_.setLock("lastRestart",  0)

        if not _force_restart_:
            player = xbmc.Player()
            isPlaying = player.isPlayingVideo()
            if isPlaying:
                playingNow = player.getPlayingFile()
                if playingNow.startswith("pvr://"):
                    logNtc("Player is currently playing a pvr channel, not restarting")
                    return

        dialog_id = xbmcgui.getCurrentWindowId()
        if dialog_id == 10100 or (dialog_id >= 10600 and dialog_id < 10800):
            xbmc.executebuiltin("ActivateWindow(home)")
            xbmc.sleep(1000)

        pluginDetails = _jsonRPC_._getAddonDetails("pvr.iptvsimple")
        if pluginDetails:
            #logDbg("Plugin details response: "+_toString(pluginDetails))
            enabled = pluginDetails["enabled"]
            if enabled:
                logNtc("Stopping IPTV Simple PVR manager")
                response = _jsonRPC_._setAddonEnabled("pvr.iptvsimple", False)
                if response:
                    logNtc("Starting IPTV Simple PVR manager")
                    response = _jsonRPC_._setAddonEnabled("pvr.iptvsimple", True)
                    if response:
                        if _notification_pvr_restart_:
                            notificationInfo(_lang_(30253))
                        else:
                            logNtc(_lang_(30253))
                        _db_.setLock("lastRestart",  time.time())
                        return True
                    else:
                        # Couldn't enable the plugin
                        return False
                else:
                    # Couldn't disable the plugin
                    return False
            else:
                # plugin is disabled
                logNtc("Starting IPTV Simple PVR manager")
                response = _jsonRPC_._setAddonEnabled("pvr.iptvsimple", True)
                if response:
                    logNtc("IPTV Simple PVR manager start done")
                    if _notification_pvr_restart_:
                        notificationInfo(_lang_(30254))
                    else:
                        logNtc(_lang_(30254))
                    _db_.setLock("lastRestart",  time.time())
                    return True
                else:
                    # Couldn't enable the plugin
                    return False
        else:
            # Couldn't get plugin details
            return False

    def _merge_additional_epg_xml(et_tv, test=False):
        logNtc("Starting merge of additional epg xml files to '"+_xmltv_+"'")
        if test:
            et_tv = etree.Element("tv")
            et_programme = etree.SubElement(et_tv, "programme", id="prg1")
            et_programme.set("start", "201701142000")
            et_programme.set("stop", "201701142100")
            etree.SubElement(et_programme, "title", lang="sk").text = "title"
            logDbg(etree.tostring(et_tv, encoding='utf8'))
        #else:
            #return et_tv, False
        ##^temporary
        additional_xml_file_list = glob.glob(_xmltv_additional_filelist_pattern_)
        if additional_xml_file_list:
            #logDbg('Found the following additional epg xml files:')
            #logDbg(additional_xml_file_list)
            for filepath in additional_xml_file_list:
                additional_xml_file = gzip.open(filepath, 'r')
                additional_xml = additional_xml_file.read()
                additional_xml_file.close()
                if additional_xml:
                    logNtc("Starting merge of epg from file '"+filepath+"'")
                    et_tv = _merge_additional_epg_xml_from_filecontents(et_tv, additional_xml)
                else:
                    logErr("Could not open '"+filepath+"' for reading")
                    return et_tv, False
        else:
            additionalXML = False
            if os.path.exists(_xmltv_additional_):
                additional_xml_file = open(_xmltv_additional_, 'r')
                additional_xml = additional_xml_file.read()
                additional_xml_file.close()
                additionalXML = True
                filepath = _xmltv_additional_
            elif os.path.exists(_xmltv_additional_gzip_):
                additional_xml_file = gzip.open(_xmltv_additional_gzip_, 'r')
                additional_xml = additional_xml_file.read()
                additional_xml_file.close()
                additionalXML = True
                filepath = _xmltv_additional_gzip_
            if additionalXML:
                if additional_xml:
                    logNtc("Starting merge of epg from file '"+filepath+"'")
                    et_tv = _merge_additional_epg_xml_from_filecontents(et_tv, additional_xml)
                else:
                    logErr("Could not open '"+filepath+"' for reading")
                    return et_tv, False
        if test:
#            xmlElTree = etree.ElementTree(et_tv)
            xmlString = etree.tostring(et_tv, encoding='utf8')
            xmltv_file = open(_xmltv_test_output_file_, 'w+')
            if xmltv_file:
                xmltv_file.write(xmlString)
                xmltv_file.close()
                logNtc("'"+_xmltv_test_output_file_+"' file saved successfully")
        return et_tv, True

    def _merge_additional_epg_xml_from_filecontents(et_tv, additional_xml):
        additional_channel_list = _getAdditionalChannelNames()
        #parser = etree.XMLParser(encoding="utf-8") #only in v >=2.7
        #additional_xml_root = etree.fromstring(additional_xml, parser=parser) #only in v >=2.7
        additional_xml_root = etree.fromstring(additional_xml)
        for channel_id in additional_channel_list:
            logNtc("Looking for 'channel' tag for '"+channel_id+"'")
            #channel_elem = additional_xml_root.find("channel[@id='"+channel_id+"']") #only in v >=2.7
            channel_elem = None
            channel_elems = additional_xml_root.findall("channel")
            for chelem in channel_elems:
                if chelem.attrib.get('id') == channel_id:
                    channel_elem = chelem
                    break
            if channel_elem:
                logNtc("Found 'channel' tag for '"+channel_id+"'")
                et_tv.append(channel_elem)
            logNtc("Looking for 'programme' tags for '"+channel_id+"'")
            #program_elems = additional_xml_root.findall("programme[@channel='"+channel_id+"']") #only in v >=2.7
            program_elems = additional_xml_root.findall("programme")
            if program_elems:
                logged = False
                for program_elem in program_elems:
                    if program_elem.attrib.get('channel') == channel_id:
                        if not logged:
                            logNtc("Found 'programme' tags for '"+channel_id+"'")
                            logged = True
                        et_tv.append(program_elem)
        return et_tv

    def _getAdditionalChannelNames():
        if _use_additional_m3u_ and os.path.exists(_m3u_additional_):
            additional_m3u = open(_m3u_additional_, 'r')
            if additional_m3u:
                additional_prgs = additional_m3u.read()
                additional_m3u.close()
            else:
                logErr("Could not open 'o2tvgo-prgs-additional.m3u' for reading")
                return []
        else:
            return []
        iterator = re.finditer('(?<=tvg-id=")[^"]*(?=")', additional_prgs, re.DOTALL | re.MULTILINE)
        return [additional_prgs[m.start():m.end()] for m in iterator]

    def _timestampishToEpgTime(timestamp):
        return datetime.datetime.fromtimestamp(
            _timestampishToTimestamp(timestamp)
        ).strftime('%Y%m%d%H%M%S')

    def _timestampishToTime(timestamp):
        return datetime.datetime.fromtimestamp(
            _timestampishToTimestamp(timestamp)
        ).strftime('%H:%M')

    def _timestampishToEpgHistoryTime(timestamp):
        return datetime.datetime.fromtimestamp(
            _timestampishToTimestamp(timestamp)
        ).strftime('%Y%m%dT%H%M%S')

    def _timestampishToTimestamp(timestamp):
        return int(timestamp)/1000

    def getChannelKeyPvr(playingNow):
        return False #TODO: convert to DB if needed#
        #logDbg(playingNow)
        aPlayingNow = playingNow.split('/')
        sPlayingNowFileName = aPlayingNow[-1]
        aPlayingNowFileName = sPlayingNowFileName.split('.')
        channelIndex = aPlayingNowFileName[0]
        with open(_m3u_json_) as data_file:
            channels = json.load(data_file)
        channelKey = channels["keysByIndex"][channelIndex]
        return channelIndex, channelKey

    def getChannelKeyVideo(playingNow):
        return False #TODO: convert to DB if needed#
        aPlayingNow = playingNow.split('/')
        sPlayingNowFileName = aPlayingNow[-1]
        aPlayingNowFileName = sPlayingNowFileName.split('.')
        sPlayingNowFileNameBase = aPlayingNowFileName[0]
        aParts = sPlayingNowFileNameBase.split('-')
        iCount = len(aParts)
        if iCount == 5:
            sChannelBaseName = sPlayingNowFileNameBase.rsplit('-', 2)[0]
        elif iCount == 4:
            sChannelBaseName = sPlayingNowFileNameBase.rpartition('-')[0]
        else:
            return None, None
        # Instead of this, just get the channel by its baseName #
        with open(_m3u_json_) as data_file:
            channels = json.load(data_file)
        channelIndex = channels["indexesByBaseNames"][sChannelBaseName]
        channelKey = channels["keysByIndex"][channelIndex]
        return channelIndex, channelKey

    def getChannelKeyByIndex(channelIndex):
        return False #TODO: convert to DB if needed#
        with open(_m3u_json_) as data_file:
            channels = json.load(data_file)
        channelKey = channels["keysByIndex"][str(channelIndex)]
        #logNtc(channelKey)
        return channelKey

    def getChannelJsonNumberByIndex(channelIndex):
        return False #TODO: convert to DB if needed#
        with open(_m3u_json_) as data_file:
            channels = json.load(data_file)
        if "chJsNumByIndex" in channels:
            channelJsonNumber = channels["chJsNumByIndex"][str(channelIndex)]
        else:
            channelJsonNumber = channelIndex
        #logNtc(channelJsonNumber)
        return channelJsonNumber

    def getEpgByChannelIndexAndTimestamp(channelIndex, timestamp):
        return False #TODO: convert to DB if needed#
        channelJsonNumber = getChannelJsonNumberByIndex(channelIndex)
        jsonEpgFilePath = _xmltv_json_base_ + str(channelJsonNumber) + ".json"
        jsonEpgFile = xbmc.translatePath(jsonEpgFilePath)
        with open(jsonEpgFile) as data_file:
            epg = json.load(data_file)

        epgNowKey = None
        epgNow = None
        startPos = None
        for key in sorted(epg.iterkeys()):
            if epg[key]["start"] == timestamp:
                epgNowKey = key
                epgNow = epg[key]
                startPos = timestamp - int(epg[key]["start"])
                return epgNowKey, epgNow, startPos
        
        for key in sorted(epg.iterkeys()):
            if epg[key]["start"] <= timestamp and timestamp <= epg[key]["end"]:
                epgNowKey = key
                epgNow = epg[key]
                startPos = timestamp - int(epg[key]["start"])
                return epgNowKey, epgNow, startPos
        return None, None, None

    def getChannelTimeshiftUrl(epg, channelKey, toTimestamp = None):
        global _o2tvgo_
        objChannel = LiveChannel(_o2tvgo_, channelKey,  None,  None,  None)
        startTimestamp = epg["startTimestamp"]
        if not toTimestamp:
            toTimestamp = epg["endTimestamp"]

        channelUrlTimeshift = objChannel.urlTimeshift(startTimestamp, toTimestamp)
        logNtc("timeshift: " + channelUrlTimeshift)

        return channelUrlTimeshift

    def getChannelStartoverUrl(epg, channelKey):
        global _o2tvgo_
        objChannel = LiveChannel(_o2tvgo_, channelKey,  None,  None,  None)
        startTimestamp = epg["startTimestamp"]

        channelUrlStartover = objChannel.urlStartover(startTimestamp)
        logNtc("startover: " + channelUrlStartover)

        return channelUrlStartover

    def setWatchPosition(epgId, watchPosition):
        global _o2tvgo_
        _o2tvgo_.setWatchPosition(epgId, watchPosition)

    def getTimestampFromDayTime(day, sTime):
        if len(day) == 3:
            days = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
        else:
            days = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
        dayWeekday = days[day]
        todayWeekday = datetime.datetime.today().weekday()
        if dayWeekday <= todayWeekday:
            diff = todayWeekday - dayWeekday
        else:
            dayWeekday -= 7
            diff = todayWeekday - dayWeekday
        date = datetime.datetime.today() - datetime.timedelta(days=diff)
        sDateTime = date.strftime('%Y%m%d')+" "+sTime
        try:
            dateTime = datetime.datetime.strptime(sDateTime, "%Y%m%d %H:%M")
        except TypeError:
            dateTime = datetime.datetime(*(time.strptime(sDateTime, "%Y%m%d %H:%M")[0:6]))
        timeDelta = (dateTime - datetime.datetime(1970, 1, 1))
        epgShift = _epgTimeshift_ * 60 * 60
        timestamp = timeDelta.total_seconds() + epgShift
        return int(timestamp)

    def playChannelFromEpg(startTime, startDate, channelName, channelNumber, playingCurrently=False, startTimestamp=None, channelIndex=None):
        player = xbmc.Player()

        logNtc("playing from epg")
        #logDbg(startDate)
        #logDbg(startTime)
        #logDbg(channelName)

        
        if startTimestamp:
            timestamp = int(startTimestamp)
        else:
            if playingCurrently:
                timestamp = int(time.time())
            else:
                timestamp = getTimestampFromDayTime(startDate, startTime)
                #logDbg(timestamp)

            if not timestamp:
                notificationError(_lang_(30504))
                logDbg([startDate, startTime, channelName])
                return

        channelRow = _db_.getChannelRow(nameOld = channelName)
        if not channelRow:
            notificationError(_lang_(30505))
            
            return
        epg = _db_.getEpgRowByStart(start = timestamp, channelID = channelRow["id"])
        if not epg:
            notificationError(_lang_(30506))
            logDbg([channelRow, timestamp, epg])
            return
        channelKey = channelRow["key"]
        #startPos = timestamp - int(epg["start"])

        timeShift = _epgTimeshift_ * 60 * 60
        timestampNow = int(time.time()) * 1000
        if timestampNow < epg["endTimestamp"] + timeShift:
            if timestampNow < epg["startTimestamp"] + timeShift:
                notificationWarning(_lang_(30260) % epg["title"])
                return
            notificationWarning(_lang_(30261) % epg["title"])
            return
            notificationInfo(_lang_(30256) % epg["title"])
            #endTimestamp = timestampNow
            #channelUrlNew = getChannelTimeshiftUrl(epg, channelKey, endTimestamp)
            channelUrlNew = getChannelStartoverUrl(epg, channelKey)
        else:
            notificationInfo(_lang_(30255) % epg["title"])
            endTimestamp = epg["endTimestamp"]
            channelUrlNew = getChannelTimeshiftUrl(epg, channelKey, endTimestamp)

        pl=xbmc.PlayList(1)
        pl.clear()
        li = xbmcgui.ListItem(epg["title"])

        if "fanart_image" in epg and epg["fanart_image"] and len(epg["fanart_image"]) > 0:
            li.setArt({
              'icon': epg["fanart_image"],
              "fanart": epg["fanart_image"],
              "poster": epg["fanart_image"]
            })
        videoinfo = {}
        if "plot" in epg and epg["plot"] and len(epg["plot"]) > 0:
            videoinfo['plot'] = epg['plot']
        if "plotoutline" in epg and epg["plotoutline"] and len(epg["plotoutline"]) > 0:
            videoinfo['plotoutline'] = epg['plotoutline']
        if "genre" in epg and epg["genre"]:
            videoinfo['genre'] = epg["genre"]
        if len(videoinfo) > 0:
            li.setInfo('video', videoinfo)

        player.play(channelUrlNew, li)
        _db_.clearCurrentlyPlaying()
        _db_.clearNextProgramme()
        _db_.updateEpg(id = epg["id"], channelID = channelRow["id"], isCurrentlyPlaying = 1, inProgressTime = 1)

        logDbg("Looking for next programme")
        timestampNext = int(epg["end"])
#        epgKeyNext, epgNext, startPosNext = getEpgByChannelIndexAndTimestamp(channelIndex, timestampNext)

        epgNext = _db_.getEpgRowByStart(start = timestampNext, channelID = channelRow["id"])
        if not epgNext:
            logErr("Didn't find next programme in epg")
            logDbg([channelRow, timestamp, epg])
        else:
            _db_.updateEpg(id = epgNext["id"], channelID = channelRow["id"], isNextProgramme = 1)

    def pausePlayer(channelNumber = None):
        return False #TODO: convert to DB if needed#
        logNtc("pausing")
        player = xbmc.Player()
        isPlaying = player.isPlayingVideo()
        if not isPlaying:
            logNtc("not playing: nothing to pause")
            return
        playingNow = player.getPlayingFile()
        channelIndex = None
        channelKey = None
        if playingNow.startswith("pvr://"):
            logNtc("playing pvr")
            if channelNumber:
                channelIndex = int(channelNumber) - 1
                channelKey = getChannelKeyByIndex(channelIndex)
            else:
                channelIndex, channelKey = getChannelKeyPvr(playingNow)
        elif playingNow.endswith("m3u8"):
            logNtc("not playing pvr")
            channelIndex, channelKey = getChannelKeyVideo(playingNow)
            if not channelKey:
                logErr("not playing O2TVGO stream")
                logDbg([playingNow, channelIndex, channelKey])
                return

        timestampNow = int(time.time())
        epgNowKey, epgNow, startPos = getEpgByChannelIndexAndTimestamp(channelIndex, timestampNow)
        if not epgNowKey or not epgNow or (not startPos and startPos != 0):
            notificationError(_lang_(30506))
            logDbg([channelIndex, timestampNow, epgNowKey, epgNow, startPos])
            return

#        toTimestamp = timestampNow * 1000
        #channelUrlNew = getChannelTimeshiftUrl(epgNow, channelKey, toTimestamp)
        channelUrlNew = getChannelStartoverUrl(epgNow, channelKey)

        pl=xbmc.PlayList(1)
        pl.clear()
        li = xbmcgui.ListItem(epgNow["title"])

        player.play(channelUrlNew, li)
        setWatchPosition(epgNow["epgId"], startPos)

        player.pause()

    def logPlayingInfo():
        return False #TODO: convert to DB if needed#
        player = xbmc.Player()
        isPlaying = player.isPlayingVideo()
        if not isPlaying:
            logNtc("PlayingInfo: not playing")
            return
        playingNow = player.getPlayingFile()
        channelIndex = None
        channelKey = None
        if playingNow.startswith("pvr://"):
            logNtc("PlayingInfo: playing pvr")
            channelIndex, channelKey = getChannelKeyPvr(playingNow)
        elif playingNow.endswith("m3u8"):
            logNtc("PlayingInfo: playing m3u8 playlist file")
            channelIndex, channelKey = getChannelKeyVideo(playingNow)
            if not channelKey:
                logNtc("PlayingInfo: not playing an O2TVGO stream")
                logDbg(playingNow)
                return

        logNtc(channelIndex)
        logNtc(channelKey)
        return

    def _test():
        logNtc("Executing _test()")
        logNtc("Nothing to do defined in _test()")

    def get_params():
            param=[]
            paramstring=sys.argv[2]
            if len(paramstring)>=2:
                    params=sys.argv[2]
                    cleanedparams=params.replace('?','')
                    if (params[len(params)-1]=='/'):
                            params=params[0:len(params)-2]
                    pairsofparams=cleanedparams.split('&')
                    param={}
                    for i in range(len(pairsofparams)):
                            splitparams={}
                            splitparams=pairsofparams[i].split('=')
                            if (len(splitparams))==2:
                                    param[splitparams[0]]=splitparams[1]
            return param

    def assign_params(params):
        for param in params:
            try:
                globals()[param]=urllib.unquote_plus(params[param])
            except:
                pass

    # Get rid of the JSON files and store all in DB #
    upgradeConfigsFromJsonToDb()
    
    pause=None
    saveepg=None
    forcenotifications=None
    showlogs=None
    mergeepg=None
    test=None
    showplayinginfo=None
    playfromepg=None
    starttime=None
    startdate=None
    channelname=None
    channelnumber=None
    playingcurrently=None
    starttimestamp=None
    channelindex=None
    iptv_simple_settings=None

    params=get_params()
    assign_params(params)

#    logDbg(params)

    if saveepg:
        forceNotifications = (forcenotifications and forcenotifications == '1')
#        logDbg(forcenotifications)
#        logDbg(_toString(forceNotifications))
        ok = saveChannels(True, forceNotifications)
        if ok:
            ok = saveEPG(False, forceNotifications)
    elif playfromepg:
        playChannelFromEpg(starttime, startdate, channelname, channelnumber, playingcurrently, starttimestamp, channelindex)
    elif iptv_simple_settings:
        _openIptvSimpleClientSettings()
    elif showlogs:
        showLogs()
    elif mergeepg:
        _merge_additional_epg_xml(None, True)
    elif pause:
        # Attempt to implement startover - not successful (yet)
        pausePlayer(channelnumber)
    elif showplayinginfo:
        logPlayingInfo()
    elif test:
        _test()
    else:
        dirListing()
    _db_.closeDB()
except Exception as ex:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    _logs_ = Logs(_scriptname_)
    xbmcgui.Dialog().notification(_scriptname_, _logs_._toString(exc_value), xbmcgui.NOTIFICATION_ERROR)
    _logs_.logErr(_logs_._toString(exc_value))
    _logs_.logDbg(traceback.format_exc())
#    if not _first_error_:
#        if xbmcgui.Dialog().yesno(_scriptname_, _lang_(30500), _lang_(30501)):
#            _addon_.setSetting("send_errors", "true")
#            _send_errors_ = (_addon_.getSetting('send_errors') == "true")
#        _addon_.setSetting("first_error", "true")
#        _first_error_ = (_addon_.getSetting('first_error') == "true")
#    if _send_errors_:
#        if _sendError(params, exc_type, exc_value, exc_traceback):
#            xbmcgui.Dialog().notification(_scriptname_, _lang_(30502), xbmcgui.NOTIFICATION_INFO)
#        else:
#            xbmcgui.Dialog().notification(_scriptname_, _lang_(30503), xbmcgui.NOTIFICATION_ERROR)
#            traceback.print_exception(exc_type, exc_value, exc_traceback)
