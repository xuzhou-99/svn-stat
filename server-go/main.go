package main

import (
	"fmt"
	"log"
	"os"

	"svn-stat/server-go/api"
	"svn-stat/server-go/config"

	"github.com/gin-gonic/gin"
)

func main() {
	// 加载配置
	configPath := "../config.yml"
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		log.Printf("Config file not found: %s, using default config\n", configPath)
		config.LoadConfig("") // 使用默认配置
	} else {
		if err := config.LoadConfig(configPath); err != nil {
			log.Printf("Failed to load config: %v, using default config\n", err)
			config.LoadConfig("") // 使用默认配置
		}
	}

	// 创建缓存目录
	if err := os.MkdirAll("cache", 0755); err != nil {
		log.Printf("Failed to create cache directory: %v\n", err)
	}

	// 创建日志目录
	if err := os.MkdirAll("logs", 0755); err != nil {
		log.Printf("Failed to create logs directory: %v\n", err)
	}

	// 创建 Gin 路由器
	r := gin.Default()

	// 设置静态文件目录
	r.Static("/static", "../static")

	// 设置模板目录
	r.LoadHTMLGlob("../templates/*")

	// 设置 API 路由
	api.SetupRoutes(r)

	// 获取配置
	cfg := config.GetConfig()
	port := "5000"
	if cfg.Debug {
		fmt.Printf("Starting server in debug mode on port %s\n", port)
		r.Run(":" + port)
	} else {
		fmt.Printf("Starting server in production mode on port %s\n", port)
		r.Run(":" + port)
	}
}
