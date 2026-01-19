package api

import (
	"net/http"
	"sync"
	"time"

	"svn-stat/server-go/cache"
	"svn-stat/server-go/config"
	"svn-stat/server-go/stats"
	"svn-stat/server-go/svn"

	"github.com/gin-gonic/gin"
)

type TaskStatus struct {
	Running          bool          `json:"running"`
	Progress         int            `json:"progress"`
	Message          string         `json:"message"`
	Completed        bool           `json:"completed"`
	Error             string         `json:"error,omitempty"`
	ExecutionDetails []ExecutionDetail `json:"execution_details,omitempty"`
	Results          *stats.AnalysisResults `json:"results,omitempty"`
}

type ExecutionDetail struct {
	Timestamp string `json:"timestamp"`
	Message   string `json:"message"`
	Level     string `json:"level"`
}

type StartAnalysisRequest struct {
	Branches      []BranchConfig `json:"branches"`
	BranchURL     string         `json:"branch_url"`
	Username      string         `json:"username"`
	Password      string         `json:"password"`
	RevisionRange string         `json:"revision_range"`
	StartDate     string         `json:"start_date"`
	EndDate       string         `json:"end_date"`
}

type BranchConfig struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	BranchURL string `json:"branch_url"`
	Username string `json:"username"`
	Password string `json:"password"`
}

type GetResultsRequest struct {
	StartDate string `json:"startDate"`
	EndDate   string `json:"endDate"`
}

var (
	taskStatus     *TaskStatus
	taskMutex      sync.RWMutex
	analysisResults *stats.AnalysisResults
	resultsMutex   sync.RWMutex
)

func init() {
	taskStatus = &TaskStatus{
		Running:          false,
		Progress:         0,
		Message:          "",
		Completed:        false,
		ExecutionDetails: []ExecutionDetail{},
	}
}

func SetupRoutes(r *gin.Engine) {
	r.GET("/", handleIndex)
	r.GET("/static/*filepath", handleStatic)
	r.GET("/api/status", handleStatus)
	r.POST("/api/start-analysis", handleStartAnalysis)
	r.POST("/api/results", handleGetResults)
}

func handleIndex(c *gin.Context) {
	c.File("../templates/index.html")
}

func handleStatic(c *gin.Context) {
	filepath := c.Param("filepath")
	c.File("../static/" + filepath)
}

func handleStatus(c *gin.Context) {
	taskMutex.RLock()
	defer taskMutex.RUnlock()

	response := gin.H{
		"running":           taskStatus.Running,
		"progress":          taskStatus.Progress,
		"message":           taskStatus.Message,
		"completed":         taskStatus.Completed,
		"error":             taskStatus.Error,
		"execution_details": taskStatus.ExecutionDetails,
	}

	if taskStatus.Completed {
		resultsMutex.RLock()
		response["results"] = analysisResults
		resultsMutex.RUnlock()
	}

	c.JSON(http.StatusOK, response)
}

func handleStartAnalysis(c *gin.Context) {
	taskMutex.RLock()
	if taskStatus.Running {
		taskMutex.RUnlock()
		c.JSON(http.StatusOK, gin.H{
			"success": false,
			"message": "任务正在运行中...",
		})
		return
	}
	taskMutex.RUnlock()

	var req StartAnalysisRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"message": "无效的请求参数",
		})
		return
	}

	cfg := config.GetConfig()

	taskMutex.Lock()
	taskStatus = &TaskStatus{
		Running:          true,
		Progress:         0,
		Message:          "准备开始...",
		Completed:        false,
		Error:             "",
		ExecutionDetails: []ExecutionDetail{},
	}
	taskMutex.Unlock()

	addExecutionDetail("开始执行SVN代码统计任务", "info")

	go func() {
		defer func() {
			if r := recover(); r != nil {
				taskMutex.Lock()
				taskStatus.Running = false
				taskStatus.Error = r.(string)
				taskMutex.Unlock()
			}
		}()

		if len(req.Branches) > 0 {
			executeMultiBranchAnalysis(req, cfg)
		} else {
			executeSingleBranchAnalysis(req, cfg)
		}
	}()

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "任务已启动",
	})
}

func executeSingleBranchAnalysis(req StartAnalysisRequest, cfg *config.Config) {
	branchURL := req.BranchURL
	username := req.Username
	password := req.Password
	revisionRange := req.RevisionRange
	startDate := req.StartDate
	endDate := req.EndDate

	if branchURL == "" {
		branchURL = cfg.SVNBaseURL
		username = cfg.SVNUsername
		password = cfg.SVNPassword
	}

	updateProgress(10, "正在连接SVN服务器...")
	addExecutionDetail("开始执行SVN代码统计任务", "info")

	updateProgress(30, "正在获取SVN日志...")
	log, err := svn.GetSVNLog(branchURL, username, password, revisionRange)
	if err != nil {
		updateError("获取SVN日志失败: " + err.Error())
		return
	}

	updateProgress(40, "正在解析日志...")
	commits := stats.ConvertLogEntriesToCommits(log.Entries)
	addExecutionDetail("日志解析完成，共找到 "+string(rune(len(commits)))+" 条提交记录", "info")

	if len(commits) == 0 {
		updateError("在指定日期范围内没有找到提交记录")
		return
	}

	addExecutionDetail("开始获取代码行数，共 "+string(rune(len(commits)))+" 个版本需要分析", "info")

	for i, commit := range commits {
		updateProgress(50+i*50/len(commits), "正在获取代码行数... ("+string(rune(i+1))+"/"+string(rune(len(commits)))+")")
		addExecutionDetail("分析版本 "+commit.Revision+" ("+string(rune(i+1))+"/"+string(rune(len(commits)))+")", "debug")

		linesAdded, linesDeleted, fileDetails, err := svn.GetSVNDiffWithCache(commit.BranchURL, commit.Revision, username, password, "../cache")
		if err != nil {
			addExecutionDetail("获取版本 "+commit.Revision+" 的代码行数失败: "+err.Error(), "error")
			continue
		}

		commit.LinesAdded = linesAdded
		commit.LinesDeleted = linesDeleted
		commit.FileDetails = fileDetails
	}

	updateProgress(80, "正在分析日志...")
	addExecutionDetail("生成新的统计数据", "info")

	results, err := stats.GenerateAnalysisResults(commits, startDate, endDate, revisionRange, "../cache")
	if err != nil {
		updateError("生成分析结果失败: " + err.Error())
		return
	}

	resultsMutex.Lock()
	analysisResults = results
	resultsMutex.Unlock()

	updateProgress(100, "分析完成! 共"+string(rune(len(commits)))+"条提交记录")
	addExecutionDetail("任务执行完成，共处理 "+string(rune(len(commits)))+" 条提交记录", "success")

	taskMutex.Lock()
	taskStatus.Running = false
	taskStatus.Completed = true
	taskMutex.Unlock()
}

func executeMultiBranchAnalysis(req StartAnalysisRequest, cfg *config.Config) {
	branches := req.Branches
	revisionRange := req.RevisionRange
	startDate := req.StartDate
	endDate := req.EndDate

	updateProgress(5, "正在准备分析多个分支...")
	addExecutionDetail("开始执行多分支SVN代码统计任务，共 "+string(rune(len(branches)))+" 个分支", "info")

	allLogs := []*svn.Log{}

	for i, branch := range branches {
		updateProgress(5+i*15/len(branches), "正在分析分支 "+string(rune(i+1))+"/"+string(rune(len(branches)))+"...")
		addExecutionDetail("开始分析分支 "+string(rune(i+1))+"/"+string(rune(len(branches)))+": "+branch.BranchURL, "info")

		log, err := svn.GetSVNLog(branch.BranchURL, branch.Username, branch.Password, revisionRange)
		if err != nil {
			addExecutionDetail("获取分支 "+branch.BranchURL+" 日志失败: "+err.Error(), "error")
			continue
		}

		allLogs = append(allLogs, log)
		addExecutionDetail("分支 "+branch.BranchURL+" 日志获取成功", "success")
	}

	if len(allLogs) == 0 {
		updateError("所有分支日志获取失败")
		return
	}

	updateProgress(50, "正在解析日志...")
	
	allCommits := []stats.Commit{}
	for _, log := range allLogs {
		commits := stats.ConvertLogEntriesToCommits(log.Entries)
		allCommits = append(allCommits, commits...)
	}

	addExecutionDetail("日志解析完成，共找到 "+string(rune(len(allCommits)))+" 条提交记录", "info")

	if len(allCommits) == 0 {
		updateError("在指定日期范围内没有找到提交记录")
		return
	}

	addExecutionDetail("开始获取代码行数，共 "+string(rune(len(allCommits)))+" 个版本需要分析", "info")

	for i, commit := range allCommits {
		updateProgress(50+i*50/len(allCommits), "正在获取代码行数... ("+string(rune(i+1))+"/"+string(rune(len(allCommits)))+")")
		addExecutionDetail("分析版本 "+commit.Revision+" ("+string(rune(i+1))+"/"+string(rune(len(allCommits)))+")", "debug")

		linesAdded, linesDeleted, fileDetails, err := svn.GetSVNDiffWithCache(commit.BranchURL, commit.Revision, branches[0].Username, branches[0].Password, "../cache")
		if err != nil {
			addExecutionDetail("获取版本 "+commit.Revision+" 的代码行数失败: "+err.Error(), "error")
			continue
		}

		commit.LinesAdded = linesAdded
		commit.LinesDeleted = linesDeleted
		commit.FileDetails = fileDetails
	}

	updateProgress(80, "正在分析日志...")
	addExecutionDetail("生成新的统计数据", "info")

	results, err := stats.GenerateAnalysisResults(allCommits, startDate, endDate, revisionRange, "../cache")
	if err != nil {
		updateError("生成分析结果失败: " + err.Error())
		return
	}

	resultsMutex.Lock()
	analysisResults = results
	resultsMutex.Unlock()

	updateProgress(100, "分析完成! 共"+string(rune(len(allCommits)))+"条提交记录")
	addExecutionDetail("任务执行完成，共处理 "+string(rune(len(allCommits)))+" 条提交记录", "success")

	taskMutex.Lock()
	taskStatus.Running = false
	taskStatus.Completed = true
	taskMutex.Unlock()
}

func handleGetResults(c *gin.Context) {
	var req GetResultsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"message": "无效的请求参数",
		})
		return
	}

	resultsMutex.RLock()
	defer resultsMutex.RUnlock()

	if analysisResults == nil {
		c.JSON(http.StatusOK, gin.H{
			"success": false,
			"message": "没有可用的分析结果",
		})
		return
	}

	c.JSON(http.StatusOK, analysisResults)
}

func updateProgress(progress int, message string) {
	taskMutex.Lock()
	defer taskMutex.Unlock()
	taskStatus.Progress = progress
	taskStatus.Message = message
}

func updateError(error string) {
	taskMutex.Lock()
	defer taskMutex.Unlock()
	taskStatus.Running = false
	taskStatus.Error = error
	addExecutionDetail(error, "error")
}

func addExecutionDetail(message, level string) {
	taskMutex.Lock()
	defer taskMutex.Unlock()

	detail := ExecutionDetail{
		Timestamp: time.Now().Format("2006-01-02 15:04:05"),
		Message:   message,
		Level:     level,
	}

	taskStatus.ExecutionDetails = append(taskStatus.ExecutionDetails, detail)
}
