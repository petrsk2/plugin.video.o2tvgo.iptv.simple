import sys
import xbmc

if __name__ == '__main__':
    li = sys.listitem
    action = li.getProperty("O2TVGoItem.Action.PlayFromBeginning")
#    xbmc.executebuiltin("Notification(\"Hello context items!\", \"%s\")" % action)
    xbmc.executebuiltin(action)
