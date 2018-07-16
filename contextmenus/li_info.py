import sys
#import xbmc
import xbmcgui

if __name__ == '__main__':
    li = sys.listitem
    
#    action = li.getProperty("O2TVGoItem.Action.ShowInfo")
#    xbmc.executebuiltin(action)

#    xbmc.executebuiltin("Notification(\"Hello context items!\", \"%s\")" % action)

#    xbmc.executebuiltin("Notification(\"Hello context items!\", \"%s\")" % li.getProperty("O2TVGoItem"))

    xbmcgui.Dialog().info(li)

#    epgRowID = str(li.getProperty("EpgRowID"))
#    channelID = str(li.getProperty("ChannelID"))
#    command = 'RunPlugin(plugin://plugin.video.o2tvgo.iptv.simple?showinfohome=1&epgrowid='+epgRowID+"&channelid="+channelID+')'
#    xbmc.executebuiltin(command)
