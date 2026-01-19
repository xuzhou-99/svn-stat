package stats

import (
	"fmt"
	"sort"
	"strings"
	"time"

	"svn-stat/server-go/svn"
)

type Commit struct {
	Revision     string                 `json:"revision"`
	Author       string                 `json:"author"`
	Date         string                 `json:"date"`
	DateStr      string                 `json:"date_str"`
	BranchURL    string                 `json:"branch_url"`
	FilesChanged int                    `json:"files_changed"`
	ChangedFiles []ChangedFile           `json:"changed_files"`
	Branches     []string               `json:"branches"`
	LinesAdded   int                    `json:"lines_added"`
	LinesDeleted int                    `json:"lines_deleted"`
	FileDetails  map[string]FileDetail   `json:"file_details"`
}

type ChangedFile struct {
	Path   string `json:"path"`
	Action string `json:"action"`
	Branch string `json:"branch"`
}

type FileDetail struct {
	LinesAdded  int    `json:"lines_added"`
	LinesDeleted int    `json:"lines_deleted"`
	Cached      bool   `json:"cached"`
	Author      string `json:"author"`
}

type AnalysisResults struct {
	Commits          []Commit          `json:"commits"`
	MonthlyStats     map[string]map[string]map[string]AuthorStats `json:"monthly_stats"`
	AuthorStats      map[string]AuthorStats `json:"author_stats"`
	BranchStats      map[string]BranchStats `json:"branch_stats"`
	DailyStats       map[string]map[string]map[string]AuthorStats `json:"daily_stats"`
	ChartData         ChartData          `json:"chart_data"`
	TotalCommits     int                `json:"total_commits"`
	TotalFiles      int                `json:"total_files"`
	TotalLinesAdded int                `json:"total_lines_added"`
	TotalLinesDeleted int                `json:"total_lines_deleted"`
	Filter           Filter             `json:"filter"`
}

type AuthorStats struct {
	Commits       int      `json:"commits"`
	FilesChanged  int      `json:"files_changed"`
	LinesAdded   int      `json:"lines_added"`
	LinesDeleted int      `json:"lines_deleted"`
	Branches      []string `json:"branches"`
}

type BranchStats struct {
	Commits       int      `json:"commits"`
	FilesChanged  int      `json:"files_changed"`
	LinesAdded   int      `json:"lines_added"`
	LinesDeleted int      `json:"lines_deleted"`
	Authors       []string `json:"authors"`
}

type ChartData struct {
	Months              []string          `json:"months"`
	Days                 []string          `json:"days"`
	Authors              []string          `json:"authors"`
	Branches             []string          `json:"branches"`
	MonthlyDataFiles     []ChartDataSeries `json:"monthlyDataFiles"`
	MonthlyDataLines    []ChartDataSeries `json:"monthlyDataLines"`
	DailyDataFiles       []ChartDataSeries `json:"dailyDataFiles"`
	DailyDataLines       []ChartDataSeries `json:"dailyDataLines"`
}

type ChartDataSeries struct {
	Label string `json:"label"`
	Data  []int  `json:"data"`
}

type Filter struct {
	StartDate     string `json:"start_date"`
	EndDate       string `json:"end_date"`
	RevisionRange string `json:"revision_range"`
}

func ConvertLogEntriesToCommits(entries []svn.LogEntry) []Commit {
	commits := make([]Commit, 0, len(entries))
	
	for _, entry := range entries {
		branches := make([]string, 0)
		changedFiles := make([]ChangedFile, 0, len(entry.Paths))
		
		for _, path := range entry.Paths {
			branch := extractBranch(path.Text)
			branches = append(branches, branch)
			
			changedFiles = append(changedFiles, ChangedFile{
				Path:   path.Text,
				Action: path.Action,
				Branch: branch,
			})
		}

		var branchURL string
		if len(branches) > 0 {
			if strings.HasPrefix(branches[0], "/trunk") {
				branchURL = branches[0]
			} else {
				branchURL = branches[0]
			}
		}

		commits = append(commits, Commit{
			Revision:     entry.Revision,
			Author:       entry.Author,
			Date:         entry.Date.Format(time.RFC3339),
			DateStr:      entry.Date.Format(time.RFC3339),
			BranchURL:    branchURL,
			FilesChanged: len(entry.Paths),
			ChangedFiles: changedFiles,
			Branches:     branches,
			LinesAdded:   0,
			LinesDeleted: 0,
			FileDetails:  make(map[string]FileDetail),
		})
	}

	return commits
}

func extractBranch(path string) string {
	if strings.Contains(path, "/src/main/") {
		parts := strings.Split(path, "/src/main/")
		if len(parts) > 0 {
			return parts[0]
		}
	}
	return "trunk"
}

func GenerateAnalysisResults(commits []Commit, startDate, endDate, revisionRange string, cacheDir string) (*AnalysisResults, error) {
	monthlyStats := getMonthlyStats(commits)
	authorStats := getAuthorStats(commits)
	branchStats := getBranchStats(commits)
	dailyStats := getDailyStats(commits)
	chartData := prepareChartData(monthlyStats, authorStats, branchStats, dailyStats)
	
	totalFiles := 0
	totalLinesAdded := 0
	totalLinesDeleted := 0
	
	for _, commit := range commits {
		totalFiles += commit.FilesChanged
		totalLinesAdded += commit.LinesAdded
		totalLinesDeleted += commit.LinesDeleted
	}

	results := &AnalysisResults{
		Commits:          commits,
		MonthlyStats:     monthlyStats,
		AuthorStats:      authorStats,
		BranchStats:      branchStats,
		DailyStats:       dailyStats,
		ChartData:         chartData,
		TotalCommits:     len(commits),
		TotalFiles:      totalFiles,
		TotalLinesAdded: totalLinesAdded,
		TotalLinesDeleted: totalLinesDeleted,
		Filter: Filter{
			StartDate:     startDate,
			EndDate:       endDate,
			RevisionRange: revisionRange,
		},
	}

	fmt.Printf("Analysis results generated: %d commits\n", len(commits))
	return results, nil
}

func getMonthlyStats(commits []Commit) map[string]map[string]map[string]AuthorStats {
	monthlyStats := make(map[string]map[string]map[string]AuthorStats)
	
	for _, commit := range commits {
		commitDate, _ := time.Parse(time.RFC3339, commit.Date)
		monthKey := commitDate.Format("2006-01")
		author := commit.Author
		
		for _, branch := range commit.Branches {
			if _, exists := monthlyStats[monthKey]; !exists {
				monthlyStats[monthKey] = make(map[string]map[string]AuthorStats)
			}
			if _, exists := monthlyStats[monthKey][branch]; !exists {
				monthlyStats[monthKey][branch] = make(map[string]AuthorStats)
			}
			if _, exists := monthlyStats[monthKey][branch][author]; !exists {
				monthlyStats[monthKey][branch][author] = AuthorStats{}
			}
			
			stats := monthlyStats[monthKey][branch][author]
			stats.FilesChanged += commit.FilesChanged
			stats.LinesAdded += commit.LinesAdded
			stats.LinesDeleted += commit.LinesDeleted
		}
	}
	
	return monthlyStats
}

func getAuthorStats(commits []Commit) map[string]AuthorStats {
	authorStats := make(map[string]AuthorStats)
	
	for _, commit := range commits {
		author := commit.Author
		
		if _, exists := authorStats[author]; !exists {
			authorStats[author] = AuthorStats{
				Branches: make([]string, 0),
			}
		}
		
		stats := authorStats[author]
		stats.Commits++
		stats.FilesChanged += commit.FilesChanged
		stats.LinesAdded += commit.LinesAdded
		stats.LinesDeleted += commit.LinesDeleted
		
		for _, branch := range commit.Branches {
			found := false
			for _, b := range stats.Branches {
				if b == branch {
					found = true
					break
				}
			}
			if !found {
				stats.Branches = append(stats.Branches, branch)
			}
		}
	}
	
	return authorStats
}

func getBranchStats(commits []Commit) map[string]BranchStats {
	branchStats := make(map[string]BranchStats)
	
	for _, commit := range commits {
		for _, branch := range commit.Branches {
			if _, exists := branchStats[branch]; !exists {
				branchStats[branch] = BranchStats{
					Authors: make([]string, 0),
				}
			}
			
			stats := branchStats[branch]
			stats.Commits++
			stats.FilesChanged += commit.FilesChanged
			stats.LinesAdded += commit.LinesAdded
			stats.LinesDeleted += commit.LinesDeleted
			
			found := false
			for _, a := range stats.Authors {
				if a == commit.Author {
					found = true
					break
				}
			}
			if !found {
				stats.Authors = append(stats.Authors, commit.Author)
			}
		}
	}
	
	return branchStats
}

func getDailyStats(commits []Commit) map[string]map[string]map[string]AuthorStats {
	dailyStats := make(map[string]map[string]map[string]AuthorStats)
	
	for _, commit := range commits {
		commitDate, _ := time.Parse(time.RFC3339, commit.Date)
		dayKey := commitDate.Format("2006-01-02")
		author := commit.Author
		
		for _, branch := range commit.Branches {
			if _, exists := dailyStats[dayKey]; !exists {
				dailyStats[dayKey] = make(map[string]map[string]AuthorStats)
			}
			if _, exists := dailyStats[dayKey][branch]; !exists {
				dailyStats[dayKey][branch] = make(map[string]AuthorStats)
			}
			if _, exists := dailyStats[dayKey][branch][author]; !exists {
				dailyStats[dayKey][branch][author] = AuthorStats{}
			}
			
			stats := dailyStats[dayKey][branch][author]
			stats.FilesChanged += commit.FilesChanged
			stats.LinesAdded += commit.LinesAdded
			stats.LinesDeleted += commit.LinesDeleted
		}
	}
	
	return dailyStats
}

func prepareChartData(monthlyStats map[string]map[string]map[string]AuthorStats, authorStats map[string]AuthorStats, branchStats map[string]BranchStats, dailyStats map[string]map[string]map[string]AuthorStats) ChartData {
	authors := make([]string, 0, len(authorStats))
	for author := range authorStats {
		authors = append(authors, author)
	}
	sort.Strings(authors)
	
	branches := make([]string, 0, len(branchStats))
	for branch := range branchStats {
		branches = append(branches, branch)
	}
	sort.Strings(branches)
	
	months := make([]string, 0, len(monthlyStats))
	for month := range monthlyStats {
		months = append(months, month)
	}
	sort.Strings(months)
	
	days := make([]string, 0, len(dailyStats))
	for day := range dailyStats {
		days = append(days, day)
	}
	sort.Strings(days)
	
	monthlyDataFiles := prepareMonthlyDataFiles(monthlyStats, authors, branches, months)
	monthlyDataLines := prepareMonthlyDataLines(monthlyStats, authors, branches, months)
	dailyDataFiles := prepareDailyDataFiles(dailyStats, authors, branches, days)
	dailyDataLines := prepareDailyDataLines(dailyStats, authors, branches, days)
	
	return ChartData{
		Months:           months,
		Days:              days,
		Authors:           authors,
		Branches:          branches,
		MonthlyDataFiles:  monthlyDataFiles,
		MonthlyDataLines: monthlyDataLines,
		DailyDataFiles:     dailyDataFiles,
		DailyDataLines:     dailyDataLines,
	}
}

func prepareMonthlyDataFiles(monthlyStats map[string]map[string]map[string]AuthorStats, authors []string, branches []string, months []string) []ChartDataSeries {
	data := make([]ChartDataSeries, 0, len(authors))
	
	for _, author := range authors {
		series := ChartDataSeries{
			Label: author,
			Data:  make([]int, 0, len(months)),
		}
		
		for _, month := range months {
			totalFiles := 0
			for _, branch := range branches {
				if monthData, exists := monthlyStats[month][branch]; exists {
					if authorData, exists := monthData[author]; exists {
						totalFiles += authorData.FilesChanged
					}
				}
			}
			series.Data = append(series.Data, totalFiles)
		}
		
		data = append(data, series)
	}
	
	return data
}

func prepareMonthlyDataLines(monthlyStats map[string]map[string]map[string]AuthorStats, authors []string, branches []string, months []string) []ChartDataSeries {
	data := make([]ChartDataSeries, 0, len(authors))
	
	for _, author := range authors {
		series := ChartDataSeries{
			Label: author,
			Data:  make([]int, 0, len(months)),
		}
		
		for _, month := range months {
			totalLines := 0
			for _, branch := range branches {
				if monthData, exists := monthlyStats[month][branch]; exists {
					if authorData, exists := monthData[author]; exists {
						totalLines += authorData.LinesAdded
					}
				}
			}
			series.Data = append(series.Data, totalLines)
		}
		
		data = append(data, series)
	}
	
	return data
}

func prepareDailyDataFiles(dailyStats map[string]map[string]map[string]AuthorStats, authors []string, branches []string, days []string) []ChartDataSeries {
	data := make([]ChartDataSeries, 0, len(authors))
	
	for _, author := range authors {
		series := ChartDataSeries{
			Label: author,
			Data:  make([]int, 0, len(days)),
		}
		
		for _, day := range days {
			totalFiles := 0
			for _, branch := range branches {
				if dayData, exists := dailyStats[day][branch]; exists {
					if authorData, exists := dayData[author]; exists {
						totalFiles += authorData.FilesChanged
					}
				}
			}
			series.Data = append(series.Data, totalFiles)
		}
		
		data = append(data, series)
	}
	
	return data
}

func prepareDailyDataLines(dailyStats map[string]map[string]map[string]AuthorStats, authors []string, branches []string, days []string) []ChartDataSeries {
	data := make([]ChartDataSeries, 0, len(authors))
	
	for _, author := range authors {
		series := ChartDataSeries{
			Label: author,
			Data:  make([]int, 0, len(days)),
		}
		
		for _, day := range days {
			totalLines := 0
			for _, branch := range branches {
				if dayData, exists := dailyStats[day][branch]; exists {
					if authorData, exists := dayData[author]; exists {
						totalLines += authorData.LinesAdded
					}
				}
			}
			series.Data = append(series.Data, totalLines)
		}
		
		data = append(data, series)
	}
	
	return data
}
