suppressPackageStartupMessages(library(irace))

finalize_irace <- function(
  root = normalizePath("."),
  log_file = NULL,
  main_elite_count = 5L
) {
  work <- file.path(root, "tuning", "work")
  if (is.null(log_file)) {
    candidates <- Sys.glob(file.path(work, "irace*.Rdata"))
    if (!length(candidates)) stop("Missing completed irace.Rdata")
    log_file <- candidates[which.max(file.info(candidates)$mtime)]
  }
  if (!file.exists(log_file)) stop("Missing completed irace.Rdata")

  loaded <- new.env(parent = globalenv())
  load(log_file, envir = loaded)
  if (!exists("iraceResults", envir = loaded, inherits = FALSE)) {
    stop("irace.Rdata does not contain iraceResults")
  }
  irace_results <- loaded$iraceResults
  eligible_sets <- Filter(
    function(ids) length(ids) >= main_elite_count,
    irace_results$allElites
  )
  if (!length(eligible_sets)) {
    stop("Completed irace log has no five-candidate main-race elite set")
  }
  main_ids <- as.integer(tail(eligible_sets, 1L)[[1L]])[seq_len(main_elite_count)]
  configurations <- irace_results$allConfigurations
  positions <- match(main_ids, configurations$.ID.)
  if (anyNA(positions)) stop("Main-race elite IDs are absent from allConfigurations")
  elites <- configurations[positions, , drop = FALSE]
  post_ids <- integer()
  if (!is.null(irace_results$psrace_log$elites)) {
    post_ids <- as.integer(irace_results$psrace_log$elites)
  }
  elites$main_race_order <- seq_len(nrow(elites))
  elites$postselection_selected <- elites$.ID. %in% post_ids
  elites$postselection_order <- match(elites$.ID., post_ids)
  development <- file.path(root, "results", "development")
  dir.create(development, recursive = TRUE, showWarnings = FALSE)

  write.csv(
    elites,
    file.path(development, "irace_elites_v2.csv"),
    row.names = FALSE
  )
  postselection <- if (!is.null(irace_results$psrace_log$configurations)) {
    irace_results$psrace_log$configurations
  } else {
    configurations[match(post_ids, configurations$.ID.), , drop = FALSE]
  }
  write.csv(
    postselection,
    file.path(development, "irace_postselection_v2.csv"),
    row.names = FALSE
  )
  write.csv(
    irace_results$allConfigurations,
    file.path(development, "irace_all_configurations_v2.csv"),
    row.names = FALSE
  )
  writeLines(
    c(
      "Five main-race elites advanced to full-budget survivor testing:",
      capture.output(print(elites)),
      "",
      "Optional irace post-selection subset (recorded, not used to drop survivors):",
      capture.output(print(postselection))
    ),
    file.path(work, "final_elites.txt")
  )
  writeLines(
    capture.output(printScenario(irace_results$scenario)),
    file.path(work, "scenario_used.txt")
  )
  writeLines(
    c(
      paste0("experiments=", sum(is.finite(irace_results$experiments))),
      paste0("main_race_elite_count_written=", nrow(elites)),
      paste0("postselection_count=", nrow(postselection)),
      paste0("completed_log=", basename(log_file))
    ),
    file.path(work, "_SUCCESS")
  )
  invisible(elites)
}

if (sys.nframe() == 0L) {
  finalize_irace()
}
