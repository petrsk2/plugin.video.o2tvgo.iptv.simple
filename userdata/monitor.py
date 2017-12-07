import xbmc, xbmcgui, xbmcaddon
import json, codecs, time

_addon_o2tvgo_iptvo_simple_ = xbmcaddon.Addon('plugin.video.o2tvgo.iptv.simple')
_profile_ = xbmc.translatePath(_addon_o2tvgo_iptvo_simple_.getAddonInfo('profile')).decode("utf-8")
_scriptname_ = _addon_o2tvgo_iptvo_simple_.getAddonInfo('name')

_next_programme_ = _profile_+'o2tvgo-next_programme.json'
_m3u_json_ = _profile_+'o2tvgo-prgs.json'
O2TVGO_VIDEO = False

class MyPlayer(xbmc.Player) :

        def __init__ (self):
            #xbmc.log('*** CALLBACK: __init__')
            xbmc.Player.__init__(self)

        #def onPlayBackStarted(self):
            #xbmc.log('*** CALLBACK: onPlayBackStarted')

        def onPlayBackEnded(self):
            xbmc.log('*** CALLBACK: onPlayBackEnded')
            if O2TVGO_VIDEO:
                self._maybePlayNextProgramme()

        def onPlayBackStopped(self):
            xbmc.log('*** CALLBACK: onPlayBackStopped')
            if O2TVGO_VIDEO:
                self._maybePlayNextProgramme()

        #def onPlayBackPaused(self):
            #xbmc.log('*** CALLBACK: onPlayBackPaused')

        #def onPlayBackResumed(self):
            #xbmc.log('*** CALLBACK: onPlayBackResumed')

        def _maybePlayNextProgramme(self):
            nextProgramme = None
            with open(_next_programme_) as data_file:
                nextProgramme = json.load(data_file)

            if not nextProgramme:
                return

            if nextProgramme["epgFound"] and (not nextProgramme["used"]) and (nextProgramme["channelIndex"] or nextProgramme["channelIndex"] == 0) and nextProgramme["end"] and nextProgramme["title"]:
                timestampNow = int(time.time())
                if int(nextProgramme['end']) <= timestampNow:
                    question = 'Do you want to play the next programme: '+nextProgramme["title"] + '?'
                    response = xbmcgui.Dialog().yesno(_scriptname_, question, yeslabel='Yes', nolabel='No')

                    if response:
                        command = 'RunPlugin(plugin://plugin.video.o2tvgo.iptv.simple?playfromepg=1&starttimestamp='
                        command += str(nextProgramme["start"])
                        command += '&channelindex='
                        command += str(nextProgramme["channelIndex"])
                        command += ')'
                        xbmc.log('*** command: '+command)
                        xbmc.executebuiltin(command)

                else:
                    position = timestampNow - int(nextProgramme['start'])
                    length = int(nextProgramme['end']) - int(nextProgramme['start'])
                    lengthMin = length / 60
                    positionMinutes = position / 60
                    positionPercent = 10000 * position / length * 0.01
                    question = 'Do you want to switch to the currently playing programme on '+nextProgramme["channelKey"]+': '+nextProgramme["title"] + ' (' + str(positionMinutes) + ' / ' + str(lengthMin) + ' min [' + str(positionPercent) + '%])?'
                    response = xbmcgui.Dialog().yesno(_scriptname_, question, yeslabel='Yes', nolabel='No')

                    if response:
                        payload = {
                          "jsonrpc": "2.0",
                          "id":"1",
                          "method": "PVR.GetChannels",
                          "params": {
                            "channelgroupid": "alltv"
                          }
                        }
                        payloadJson = json.dumps(payload)
                        jsonResponse = xbmc.executeJSONRPC(payloadJson)
                        if jsonResponse:
                            response = json.loads(jsonResponse)

                        channelID = None
                        if "result" in response and "channels" in response["result"]:
                            channels = response["result"]["channels"]
                            for channel in channels:
                                if channel["label"] == nextProgramme["channelName"]:
                                    channelID = channel["channelid"]
                                    break
                        if not channelID and channelID != 0:
                            xbmc.log("*** Could not find the channel's ID")
                            xbmc.log('*** channelName: '+nextProgramme["channelName"])
                            xbmc.log('*** channels: '+jsonResponse)
                        else:
                            payload = {
                              "jsonrpc": "2.0",
                              "id":"1",
                              "method": "Player.Open",
                              "params": {
                                "item":{
                                  "channelid": channelID
                                }
                              }
                            }
                            payloadJson = json.dumps(payload)
                            jsonResponse = xbmc.executeJSONRPC(payloadJson)
                            if jsonResponse:
                                responseDecoded = json.loads(jsonResponse)
                                if "error" in responseDecoded:
                                    if "message" in responseDecoded["error"]:
                                        xbmc.log("*** Could not play "+nextProgramme["channelKey"]+": "+responseDecoded["error"]["message"])
                                    else:
                                        xbmc.log("*** Could not play "+nextProgramme["channelKey"])
                                    xbmc.log('*** payloadJson: '+payloadJson)
                                    xbmc.log('*** jsonResponse: '+jsonResponse)
                            else:
                                xbmc.log("*** Could not play "+nextProgramme["channelKey"]+": No response from JSONRPC")
                                xbmc.log('*** payloadJson: '+payloadJson)
                                xbmc.log('*** jsonResponse: '+jsonResponse)


            nextProgramme["used"] = True
            with open(_next_programme_, 'wb') as f:
                json.dump(nextProgramme, codecs.getwriter('utf-8')(f), ensure_ascii=False)


player=MyPlayer()

def isPlayingVideoO2TVGO():
    playingNow = xbmc.Player().getPlayingFile()
    nextProgramme = None
    with open(_next_programme_) as data_file:
        nextProgramme = json.load(data_file)

    if not nextProgramme:
        return False

    if not "currentUrl" in nextProgramme:
        return False

    if nextProgramme["currentUrl"] == playingNow:
        #xbmc.log('*** isPlayingVideoO2TVGO: matched!')
        return True

    if not playingNow.endswith("m3u8"):
        #xbmc.log('*** isPlayingVideoO2TVGO: not playing m3u8')
        return False
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
        return False

    channels = False
    with open(_m3u_json_) as data_file:
        channels = json.load(data_file)
    if not channels:
        xbmc.log('*** isPlayingVideoO2TVGO: No channels found')
        xbmc.log(str(channels))
        return False

    if not sChannelBaseName in channels["indexesByBaseNames"]:
        xbmc.log('*** isPlayingVideoO2TVGO: not playing O2TVGO stream: channel name not found in channels["indexesByBaseNames"]')
        xbmc.log(playingNow)
        xbmc.log(sChannelBaseName)
        return False

    channelIndex = channels["indexesByBaseNames"][sChannelBaseName]
    if not channelIndex and channelIndex != 0:
        xbmc.log('*** isPlayingVideoO2TVGO: not playing O2TVGO stream')
        xbmc.log(str(channelIndex))
        return False

    channelKey = channels["keysByIndex"][str(channelIndex)]
    if not channelKey:
        xbmc.log('*** isPlayingVideoO2TVGO: not playing O2TVGO stream')
        xbmc.log(str(channelKey))
        return False
    return True

monitor = xbmc.Monitor()

while not monitor.abortRequested() and not xbmc.abortRequested:
    # Sleep/wait for abort for 5 seconds
    if monitor.waitForAbort(4) or xbmc.abortRequested:
        # Abort was requested while waiting. We should exit
        xbmc.log("abort was requested")
        break

    if xbmc.Player().isPlayingVideo():
        try:
            O2TVGO_VIDEO = isPlayingVideoO2TVGO()
        except:
            e = sys.exc_info()[0]
            xbmc.log('*** isPlayingVideoO2TVGO exception: ' + str(e))
            O2TVGO_VIDEO = False

    else:
        O2TVGO_VIDEO = False
