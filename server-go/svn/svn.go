package svn

import (
	"bufio"
	"bytes"
	"encoding/xml"
	"fmt"
	"os/exec"
	"strings"
	"time"
	"crypto/md5"
	"regexp"
	"svn-stat/server-go/cache"
)

type LogEntry struct {
	Revision    string    `xml:"revision,attr"`
	Author      string    `xml:"author"`
	Date        time.Time `xml:"date"`
	Paths       []Path    `xml:"paths>path"`
	Message     string    `xml:"msg"`
}

type Path struct {
	Action string `xml:"action,attr"`
	Kind   string `xml:"kind,attr"`
	Text   string `xml:",chardata"`
}

type Log struct {
	XMLName xml.Name `xml:"log"`
	Entries []LogEntry `xml:"logentry"`
}

func GetSVNLog(branchURL, username, password, revisionRange string) (*Log, error) {
	cmd := exec.Command("svn", "log", "--xml", "--verbose", "--no-auth-cache")
	
	if username != "" {
		cmd.Args = append(cmd.Args, "--username", username)
	}
	if password != "" {
		cmd.Args = append(cmd.Args, "--password", password)
	}
	if revisionRange != "" {
		cmd.Args = append(cmd.Args, "-r", revisionRange)
	}
	cmd.Args = append(cmd.Args, branchURL)

	fmt.Printf("Executing SVN log command: %v\n", cmd.Args)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("SVN log command failed: %w, stderr: %s", err, stderr.String())
	}

	var log Log
	if err := xml.Unmarshal(stdout.Bytes(), &log); err != nil {
		return nil, fmt.Errorf("failed to parse SVN log XML: %w", err)
	}

	fmt.Printf("SVN log retrieved: %d entries\n", len(log.Entries))
	return &log, nil
}

func GetSVNDiff(branchURL, revision, username, password string) (string, error) {
	cmd := exec.Command("svn", "diff", "-c", revision, "--no-auth-cache")
	
	if username != "" {
		cmd.Args = append(cmd.Args, "--username", username)
	}
	if password != "" {
		cmd.Args = append(cmd.Args, "--password", password)
	}
	cmd.Args = append(cmd.Args, branchURL)

	fmt.Printf("Executing SVN diff command for revision %s\n", revision)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("SVN diff command failed: %w, stderr: %s", err, stderr.String())
	}

	return stdout.String(), nil
}

func GetSVNFileContent(branchURL, revision, filePath, username, password string) (string, error) {
	cmd := exec.Command("svn", "cat", "-r"+revision, fmt.Sprintf("%s/%s", branchURL, filePath))
	
	if username != "" {
		cmd.Args = append(cmd.Args, "--username", username)
	}
	if password != "" {
		cmd.Args = append(cmd.Args, "--password", password)
	}

	fmt.Printf("Executing SVN cat command for revision %s, file %s\n", revision, filePath)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("SVN cat command failed: %w, stderr: %s", err, stderr.String())
	}

	return stdout.String(), nil
}

func GetSVNExternals(branchURL, username, password string) ([]map[string]string, error) {
	cmd := exec.Command("svn", "propget", "svn:externals", "--no-auth-cache")
	
	if username != "" {
		cmd.Args = append(cmd.Args, "--username", username)
	}
	if password != "" {
		cmd.Args = append(cmd.Args, "--password", password)
	}
	cmd.Args = append(cmd.Args, branchURL)

	fmt.Printf("Executing SVN propget command for externals\n")

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("SVN propget command failed: %w, stderr: %s", err, stderr.String())
	}

	externals := make([]map[string]string, 0)
	scanner := bufio.NewScanner(&stdout)
	
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}

		parts := strings.Fields(line)
		if len(parts) >= 2 {
			external := map[string]string{
				"path": parts[0],
				"url":  parts[1],
			}
			externals = append(externals, external)
		}
	}

	fmt.Printf("Found %d externals\n", len(externals))
	return externals, nil
}

func GetLatestRevision(branchURL string) (string, error) {
	cmd := exec.Command("svn", "info", "--xml", branchURL)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("SVN info command failed: %w, stderr: %s", err, stderr.String())
	}

	var info struct {
		Entry struct {
			Revision string `xml:"revision,attr"`
		} `xml:"entry"`
	}

	if err := xml.Unmarshal(stdout.Bytes(), &info); err != nil {
		return "", fmt.Errorf("failed to parse SVN info XML: %w", err)
	}

	return info.Entry.Revision, nil
}


type DiffResult struct {
	LinesAdded    int                      `json:"lines_added"`
	LinesDeleted  int                      `json:"lines_deleted"`
	FileDetails  map[string]FileDetail    `json:"file_details"`
}

type FileDetail struct {
	LinesAdded  int    `json:"lines_added"`
	LinesDeleted int    `json:"lines_deleted"`
	Cached      bool   `json:"cached"`
	Author      string `json:"author"`
}

func ParseSVNDiff(diffOutput string) (int, int, map[string]FileDetail) {
	totalLinesAdded := 0
	totalLinesDeleted := 0
	fileDetails := make(map[string]FileDetail)

	fileBlockPattern := regexp.MustCompile(`---\s+(.*?)\s+\d+.*?\n\+\+\+\s+(.*?)\s+\d+.*?(?=\n---|\Z)`)
	
	matches := fileBlockPattern.FindAllStringSubmatch(diffOutput, -1)
	
	for _, match := range matches {
		if len(match) < 3 {
			continue
		}

		oldFile := strings.TrimSpace(match[1])
		newFile := strings.TrimSpace(match[2])
		
		var filePath string
		if strings.HasPrefix(oldFile, "/") {
			filePath = strings.TrimPrefix(oldFile, "/")
		} else {
			parts := strings.Split(newFile, "/")
			if len(parts) > 1 {
				filePath = strings.Join(parts[len(parts)-2:], "/")
			} else {
				filePath = parts[len(parts)-1]
			}
		}

		fileContent := match[0]
		
		linesAdded := 0
		linesDeleted := 0
		
		for _, line := range strings.Split(fileContent, "\n") {
			if strings.HasPrefix(line, "+") && !strings.HasPrefix(line, "+++") {
				linesAdded++
			} else if strings.HasPrefix(line, "-") && !strings.HasPrefix(line, "---") {
				linesDeleted++
			}
		}

		totalLinesAdded += linesAdded
		totalLinesDeleted += linesDeleted
		
		fileDetails[filePath] = FileDetail{
			LinesAdded:  linesAdded,
			LinesDeleted: linesDeleted,
			Cached:      false,
			Author:      "",
		}
	}

	return totalLinesAdded, totalLinesDeleted, fileDetails
}

func GetSVNDiffWithCache(branchURL, revision, username, password string, cacheDir string) (int, int, map[string]FileDetail, error) {
	cacheData := cache.GetCache()
	revisionCacheKey := cache.GenerateRevisionCacheKey(revision)
	
	if summary, exists := cache.GetRevisionSummaryCache(revision); exists {
		totalLinesAdded := summary.TotalLinesAdded
		totalLinesDeleted := summary.TotalLinesDeleted
		fileDetails := make(map[string]FileDetail)
		
		needRefresh := false
		
		for _, filePath := range summary.FileList {
			fileCacheKey := cache.GenerateFileCacheKey(revision, filePath)
			if fileCache, exists := cache.GetRevisionFileCache(revision, filePath); exists {
				fileDetails[filePath] = FileDetail{
					LinesAdded:  fileCache.LinesAdded,
					LinesDeleted: fileCache.LinesDeleted,
					Cached:      true,
					Author:      fileCache.Author,
				}
			} else {
				needRefresh = true
			}
		}
		
		if !needRefresh {
			fmt.Printf("Using cached diff data for revision %s\n", revision)
			return totalLinesAdded, totalLinesDeleted, fileDetails
		}
	}

	fmt.Printf("Fetching fresh diff data for revision %s\n", revision)
	diffOutput, err := GetSVNDiff(branchURL, revision, username, password)
	if err != nil {
		return 0, 0, nil, err
	}

	totalLinesAdded, totalLinesDeleted, fileDetails := ParseSVNDiff(diffOutput)
	
	for filePath, detail := range fileDetails {
		content, err := GetSVNFileContent(branchURL, revision, filePath, username, password)
		if err != nil {
			fmt.Printf("Failed to get file content for %s: %v\n", filePath, err)
			continue
		}

		hash := fmt.Sprintf("%x", md5.Sum([]byte(content)))
		
		cache.UpdateRevisionFileCache(revision, filePath, hash, detail.Author, detail.LinesAdded, detail.LinesDeleted)
	}

	fileList := make([]string, 0, len(fileDetails))
	for filePath := range fileDetails {
		fileList = append(fileList, filePath)
	}
	
	cache.UpdateRevisionSummaryCache(revision, branchURL, totalLinesAdded, totalLinesDeleted, len(fileDetails), fileList)
	
	if err := cache.SaveCache(cacheDir); err != nil {
		fmt.Printf("Failed to save cache: %v\n", err)
	}

	return totalLinesAdded, totalLinesDeleted, fileDetails, nil
}
