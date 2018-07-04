import xbmc, xbmcgui, xbmcaddon
import json, time,  sqlite3, sys,  traceback

_addon_o2tvgo_iptvo_simple_ = xbmcaddon.Addon('plugin.video.o2tvgo.iptv.simple')
_profile_ = xbmc.translatePath(_addon_o2tvgo_iptvo_simple_.getAddonInfo('profile')).decode("utf-8")
_scriptname_ = _addon_o2tvgo_iptvo_simple_.getAddonInfo('name')

_next_programme_ = _profile_+'o2tvgo-next_programme.json'
_m3u_json_ = _profile_+'o2tvgo-prgs.json'
_db_path_ = _profile_+'o2tvgo.db'
O2TVGO_VIDEO = False

class O2tvgoDBMini:
    def __init__(self,  db_path):
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.text_factory = str
        # enable foreign keys: #
        self.connection.execute("PRAGMA foreign_keys = 1")
        self.cursor = self.connection.cursor()
        
    def commit(self):
        self.connection.commit()
    
    def cexec(self, sql, vals=None):
        try:
            if vals:
                self.cursor.execute(sql, vals)
            else:
                self.cursor.execute(sql)
            self.commit()
            return self.cursor.lastrowid
        except Exception as ex:
            xbmc.log("*** Exception while executing a query ("+sql+"): "+str(ex))

    def _getEpgColumns(self):
        return ["epgId", "start", "startTimestamp", "startEpgTime", "end", "endTimestamp", "endEpgTime", "title", "plot", "plotoutline", "fanart_image", "genre", "genres", "channelID",
                  "isCurrentlyPlaying", "isNextProgramme", "inProgressTime", "isRecentlyWatched", "isWatchLater"]

    def getNextEpg(self):
        self.cexec("SELECT e.*, ch.name as channelName FROM epg e JOIN channels ch on e.channelID=ch.id WHERE e.isNextProgramme = ?",  (1, ))
        epgDict = {}
        epgColumns = self._getEpgColumns()
        for row in self.cursor:
            epgDict = {
                "id": row["id"], 
                "channelName": row["channelName"]
            }
            for col in epgColumns:
                if row[col]:
                    epgDict[col] = row[col]
            return epgDict
        return False
    
    def getCurrentlyPlayingEpg(self):
        self.cexec("SELECT e.*, ch.id as channelID, ch.name as channelName FROM epg e JOIN channels ch on e.channelID=ch.id WHERE e.isCurrentlyPlaying = ?",  (1, ))
        epgDict = {}
        epgColumns = self._getEpgColumns()
        for row in self.cursor:
            epgDict = {
                "id": row["id"], 
                "channelName": row["channelName"], 
                "channelID": row["channelID"]
            }
            for col in epgColumns:
                if row[col]:
                    epgDict[col] = row[col]
            return epgDict
        return False
    
    def getChannelByBaseName(self,  baseName):
        self.cexec("SELECT id, \"key\", keyClean, name, epgLastModTimestamp FROM channels WHERE baseName LIKE '%"+baseName+"%'")
        r = self.cursor.fetchone()
        if not r:
            return {}
        return {
            "id": r[0], 
            "key": r[1], 
            "keyClean": r[2], 
            "name": r[3], 
            "epgLastModTimestamp": r[4]
        }
    
    def setProgress(self, channelID, epgID,  time):
        self.cexec("UPDATE epg SET inProgressTime = ? WHERE channelID = ? AND id = ?",  (time, channelID,  epgID))
    
    def setIsNextProgrammeUsed(self):
        self.cexec("UPDATE epg SET isNextProgramme = ? WHERE isNextProgramme = ?",  (0, 1))
    
    def setIsCurrentlyPlayingTo0(self):
        self.cexec("UPDATE epg SET isCurrentlyPlaying = ? WHERE isCurrentlyPlaying = ?",  (0, 1))
    
    def setIsRecentlyWatchedTo1(self, epgID):
        self.cexec("UPDATE epg SET isRecentlyWatched = ? WHERE id = ?",  (1, epgID))
    
    def getLock(self, name,  silent=True):
        self.cexec("SELECT val FROM lock WHERE name = ?",  (name, ))
        all = self.cursor.fetchall()
        rowcount = len(all)
        if rowcount > 1:
            xbmc.log("More than one row match the lock search criteria for: name = "+name+"!")
            return 0
        if rowcount == 0:
            if not silent:
                xbmc.log("No row matches the channel lock criteria for: name = "+name+"!")
            return 0
        r = all[0]
        val = r[0]        
        return val

_db_ = O2tvgoDBMini(_db_path_)

class MyPlayer(xbmc.Player) :

        def __init__ (self):
            #xbmc.log('*** CALLBACK: __init__')
            xbmc.Player.__init__(self)

        #def onPlayBackStarted(self):
            #xbmc.log('*** CALLBACK: onPlayBackStarted')

        def onPlayBackEnded(self):
            xbmc.log('*** CALLBACK: onPlayBackEnded')
            _db_.setIsCurrentlyPlayingTo0()
            if O2TVGO_VIDEO:
                self._maybePlayNextProgramme()

        def onPlayBackStopped(self):
            xbmc.log('*** CALLBACK: onPlayBackStopped')
            _db_.setIsCurrentlyPlayingTo0()
            if O2TVGO_VIDEO:
                self._maybePlayNextProgramme()

        #def onPlayBackPaused(self):
            #xbmc.log('*** CALLBACK: onPlayBackPaused')

        #def onPlayBackResumed(self):
            #xbmc.log('*** CALLBACK: onPlayBackResumed')

        def _maybePlayNextProgramme(self):
            nextProgramme = _db_.getNextEpg()

            if not nextProgramme:
                return

            timestampNow = int(time.time())
            if int(nextProgramme['end']) <= timestampNow:
                question = 'Do you want to play the next programme: '+nextProgramme["title"] + '?'
                response = xbmcgui.Dialog().yesno(_scriptname_, question, yeslabel='Yes', nolabel='No')

                if response:
                    command = 'RunPlugin(plugin://plugin.video.o2tvgo.iptv.simple?playfromepg=1&starttimestamp='
                    command += str(nextProgramme["start"])
                    command += '&channelname='
                    command += str(nextProgramme["channelName"])
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

            _db_.setIsNextProgrammeUsed()


player=MyPlayer()

def isPlayingVideoO2TVGO():
    currentlyPlaying = _db_.getCurrentlyPlayingEpg()
    if currentlyPlaying:
        #epgTimeshift = _db_.getLock("timeshift")
        #timeShift = epgTimeshift * 60 * 60
        #timestampNow = int(time.time()) - int(timeShift)
        #position = timestampNow - int(currentlyPlaying['start'])
        position = int(xbmc.Player().getTime())
        length = int(currentlyPlaying['end']) - int(currentlyPlaying['start'])
        #xbmc.log('*** isPlayingVideoO2TVGO: '+str(length)+", "+str(position)+", "+str(timestampNow)+", "+currentlyPlaying["channelName"]+", "+str(currentlyPlaying["title"]))
        if length - position < 30:
            _db_.setProgress(currentlyPlaying["channelID"], currentlyPlaying["id"],  0)
            _db_.setIsRecentlyWatchedTo1(currentlyPlaying["id"])
        else:
            _db_.setProgress(currentlyPlaying["channelID"], currentlyPlaying["id"],  position)
        return True
    playingNow = xbmc.Player().getPlayingFile()
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

    channelDict = _db_.getChannelByBaseName(sChannelBaseName)
    if channelDict:
        return True
    else:
        return False

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
            exc_type, exc_value, exc_traceback = sys.exc_info()
            e = sys.exc_info()[0]
            xbmc.log('*** isPlayingVideoO2TVGO exception: ' + str(e))
            xbmc.log(traceback.format_exc())
            O2TVGO_VIDEO = False

    else:
        O2TVGO_VIDEO = False
    
#    if not O2TVGO_VIDEO:
#        _db_.setIsCurrentlyPlayingTo0()
