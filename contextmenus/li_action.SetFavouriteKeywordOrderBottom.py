import sys
import xbmc

if __name__ == '__main__':
    li = sys.listitem
    action = li.getProperty("O2TVGoItem.Action.OrderFavouriteKeywordBottom")
    xbmc.executebuiltin(action)
