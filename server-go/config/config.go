package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

type Config struct {
	SVNBaseURL    string `yaml:"svn_base_url"`
	DefaultBranch string `yaml:"default_branch"`
	Debug         bool   `yaml:"debug"`
	SVNUsername   string `yaml:"svn_username"`
	SVNPassword   string `yaml:"svn_password"`
	LogRangeDays  int    `yaml:"log_range_days"`
}

var (
	appConfig *Config
)

func LoadConfig(configPath string) (*Config, error) {
	data, err := os.ReadFile(configPath)
	if err != nil {
		return getDefaultConfig(), nil
	}

	var config Config
	if err := yaml.Unmarshal(data, &config); err != nil {
		fmt.Printf("Failed to parse config file: %v\n", err)
		return getDefaultConfig(), nil
	}

	fmt.Printf("Config loaded from %s: %+v\n", configPath, config)
	appConfig = &config
	return &config, nil
}

func GetConfig() *Config {
	if appConfig == nil {
		return getDefaultConfig()
	}
	return appConfig
}

func getDefaultConfig() *Config {
	config := &Config{
		SVNBaseURL:    "http://svn.waiqin365.com/project/iorder-saas",
		DefaultBranch: "trunk",
		Debug:         false,
		SVNUsername:   "svnuser",
		SVNPassword:   "svnpassword",
		LogRangeDays:  180,
	}
	appConfig = config
	return config
}
