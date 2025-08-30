const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Significantly reduce file watching
config.watchFolders = [];
config.resolver.platforms = ['ios', 'android'];
config.watchman = false;

// Ignore node_modules and other large directories
config.resolver.blockList = [
  /node_modules\/.*\/node_modules\/.*/,
  /\.git\/.*/,
];

module.exports = config;
