package cache

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type CacheData struct {
	Version string `json:"version"`
	Cache   Cache  `json:"cache"`
}

type Cache struct {
	RevisionFile    map[string]RevisionFileCache    `json:"revision_file"`
	RevisionSummary map[string]RevisionSummaryCache `json:"revision_summary"`
}

type RevisionFileCache struct {
	Revision     string `json:"revision"`
	FilePath     string `json:"file_path"`
	Hash         string `json:"hash"`
	Author       string `json:"author"`
	LinesAdded  int    `json:"lines_added"`
	LinesDeleted int    `json:"lines_deleted"`
	Timestamp    int64  `json:"timestamp"`
}

type RevisionSummaryCache struct {
	Revision         string   `json:"revision"`
	BranchURL        string   `json:"branch_url"`
	TotalLinesAdded  int      `json:"total_lines_added"`
	TotalLinesDeleted int      `json:"total_lines_deleted"`
	FileCount        int      `json:"file_count"`
	FileList         []string `json:"file_list"`
	Timestamp        int64    `json:"timestamp"`
}

var (
	cacheData *CacheData
	cacheMutex sync.RWMutex
)

const (
	CacheVersion = "1.1"
)

func LoadCache(cacheDir string) (*CacheData, error) {
	cacheFile := filepath.Join(cacheDir, "svn_cache.json")
	
	if _, err := os.Stat(cacheDir); os.IsNotExist(err) {
		if err := os.MkdirAll(cacheDir, 0755); err != nil {
			fmt.Printf("Failed to create cache directory: %v\n", err)
			return nil, err
		}
	}

	data, err := os.ReadFile(cacheFile)
	if err != nil {
		fmt.Printf("Cache file not found, creating new cache: %v\n", err)
		return getDefaultCache(), nil
	}

	var cache CacheData
	if err := json.Unmarshal(data, &cache); err != nil {
		fmt.Printf("Failed to parse cache file: %v\n", err)
		return getDefaultCache(), nil
	}

	cacheMutex.Lock()
	cacheData = &cache
	cacheMutex.Unlock()

	fmt.Printf("Cache loaded from %s\n", cacheFile)
	return &cache, nil
}

func SaveCache(cacheDir string) error {
	cacheMutex.RLock()
	defer cacheMutex.RUnlock()

	cacheFile := filepath.Join(cacheDir, "svn_cache.json")
	
	data, err := json.MarshalIndent(cacheData, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal cache: %w", err)
	}

	if err := os.WriteFile(cacheFile, data, 0644); err != nil {
		return fmt.Errorf("failed to write cache file: %w", err)
	}

	fmt.Printf("Cache saved to %s, size: %d bytes\n", cacheFile, len(data))
	return nil
}

func GetCache() *CacheData {
	cacheMutex.RLock()
	defer cacheMutex.RUnlock()
	
	if cacheData == nil {
		return getDefaultCache()
	}
	return cacheData
}

func getDefaultCache() *CacheData {
	cache := &CacheData{
		Version: CacheVersion,
		Cache: Cache{
			RevisionFile:    make(map[string]RevisionFileCache),
			RevisionSummary: make(map[string]RevisionSummaryCache),
		},
	}
	cacheMutex.Lock()
	cacheData = cache
	cacheMutex.Unlock()
	return cache
}

func GenerateFileCacheKey(revision, filePath string) string {
	return fmt.Sprintf("%s|%s", revision, filePath)
}

func GenerateRevisionCacheKey(revision string) string {
	return revision
}

func UpdateRevisionFileCache(revision, filePath, hash, author string, linesAdded, linesDeleted int) {
	cacheMutex.Lock()
	defer cacheMutex.Unlock()

	key := GenerateFileCacheKey(revision, filePath)
	cacheData.Cache.RevisionFile[key] = RevisionFileCache{
		Revision:     revision,
		FilePath:     filePath,
		Hash:         hash,
		Author:       author,
		LinesAdded:  linesAdded,
		LinesDeleted: linesDeleted,
		Timestamp:    time.Now().Unix(),
	}
}

func UpdateRevisionSummaryCache(revision, branchURL string, totalLinesAdded, totalLinesDeleted, fileCount int, fileList []string) {
	cacheMutex.Lock()
	defer cacheMutex.Unlock()

	key := GenerateRevisionCacheKey(revision)
	cacheData.Cache.RevisionSummary[key] = RevisionSummaryCache{
		Revision:         revision,
		BranchURL:        branchURL,
		TotalLinesAdded:  totalLinesAdded,
		TotalLinesDeleted: totalLinesDeleted,
		FileCount:        fileCount,
		FileList:         fileList,
		Timestamp:        time.Now().Unix(),
	}
}

func GetRevisionFileCache(revision, filePath string) (RevisionFileCache, bool) {
	cacheMutex.RLock()
	defer cacheMutex.RUnlock()

	key := GenerateFileCacheKey(revision, filePath)
	cache, exists := cacheData.Cache.RevisionFile[key]
	return cache, exists
}

func GetRevisionSummaryCache(revision string) (RevisionSummaryCache, bool) {
	cacheMutex.RLock()
	defer cacheMutex.RUnlock()

	key := GenerateRevisionCacheKey(revision)
	cache, exists := cacheData.Cache.RevisionSummary[key]
	return cache, exists
}
