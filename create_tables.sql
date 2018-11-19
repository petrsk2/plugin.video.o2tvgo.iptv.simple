CREATE TABLE IF NOT EXISTS channels (
	id INTEGER PRIMARY KEY ASC,
    "key" TEXT,
    keyClean TEXT,
    name TEXT,
    baseName TEXT,
    epgLastModTimestamp REAL,
    icon TEXT,
    num INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS epg (
	id INTEGER PRIMARY KEY ASC,
    epgId INTEGER,
    "start" INTEGER,
    startTimestamp INTEGER,
    startEpgTime INTEGER,
    "end" INTEGER,
    endTimestamp INTEGER,
    endEpgTime INTEGER,
    title TEXT,
    plot TEXT,
    plotoutline TEXT,
    fanart_image TEXT,
    genre TEXT,
    genres TEXT,
    channelID INTEGER REFERENCES channels(id) ON DELETE CASCADE ON UPDATE CASCADE,
    isCurrentlyPlaying INTEGER DEFAULT 0 NOT NULL,
    isNextProgramme INTEGER DEFAULT 0 NOT NULL,
    isRecentlyWatched INTEGER DEFAULT 0 NOT NULL,
    inProgressTime INTEGER DEFAULT 0 NOT NULL,
    isWatchLater INTEGER DEFAULT 0 NOT NULL
);

CREATE TABLE IF NOT EXISTS favourites (
    id INTEGER PRIMARY KEY ASC,
    title_pattern TEXT,
    "order" INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS lock (
    id INTEGER PRIMARY KEY ASC,
    name TEXT UNIQUE,
    val REAL DEFAULT 0 NOT NULL
);
