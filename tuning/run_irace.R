suppressPackageStartupMessages(library(irace))

root <- normalizePath(".")
work <- file.path(root, "tuning", "work")
dir.create(work, recursive = TRUE, showWarnings = FALSE)
recovering <- identical(Sys.getenv("IRACE_RECOVER"), "1")
log_name <- Sys.getenv(
  "IRACE_LOG_FILE",
  if (recovering) "irace_recovered.Rdata" else "irace.Rdata"
)

parameters <- readParameters(file.path(root, "tuning", "parameters.txt"))
instances <- readLines(file.path(root, "tuning", "instances.txt"), warn = FALSE)
instances <- instances[nzchar(instances)]

scenario <- list(
  execDir = root,
  parameters = parameters,
  instances = instances,
  sampleInstances = FALSE,
  blockSize = 4L,
  maxExperiments = 2000L,
  minNbSurvival = 5L,
  mu = 20L,
  testType = "friedman",
  firstTest = 5L,
  eachTest = 1L,
  targetRunner = normalizePath(file.path(root, "tuning", "target-runner")),
  targetCmdline = "{configurationID} {instanceID} {seed} {instance} {targetRunnerArgs}",
  parallel = 4L,
  loadBalancing = TRUE,
  deterministic = FALSE,
  seed = 20260902L,
  logFile = file.path(work, log_name),
  quiet = FALSE,
  debugLevel = 0L
)

if (recovering) {
  recovery <- file.path(
    work,
    Sys.getenv("IRACE_RECOVERY_FILE", "irace.Rdata")
  )
  if (!file.exists(recovery)) stop("IRACE_RECOVER=1 but no irace.Rdata exists")
  if (normalizePath(recovery) == normalizePath(scenario$logFile, mustWork = FALSE)) {
    stop("IRACE_RECOVERY_FILE and IRACE_LOG_FILE must name different files")
  }
  scenario$recoveryFile <- recovery
}

checkIraceScenario(scenario)
if (identical(Sys.getenv("IRACE_CHECK_ONLY"), "1")) {
  message("irace scenario check passed; full race was not started")
  quit(save = "no", status = 0L)
}
irace(scenario = scenario)
source(file.path(root, "tuning", "finalize_irace.R"))
finalize_irace(root, scenario$logFile)
