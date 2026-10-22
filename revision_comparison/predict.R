# Published classifier, with explicitly recorded defaults and stable ordering.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args) == 4)
train <- read.csv(args[1], check.names=FALSE, stringsAsFactors=FALSE)
test <- read.csv(args[2], check.names=FALSE, stringsAsFactors=FALSE)
features <- c("mean_profit_over_max", "mean_weight_over_max", "correlation_01")
rules <- c("DEF", "MAXP", "MAXPW", "MINW")
stopifnot(!anyDuplicated(train$name), !anyDuplicated(test$name),
          identical(train$name, sort(train$name, method="radix")),
          identical(test$name, sort(test$name, method="radix")),
          !any(train$name %in% test$name),
          all(is.finite(as.matrix(train[features]))),
          all(is.finite(as.matrix(test[features]))), all(train$label %in% rules))
RNGkind("Mersenne-Twister", "Inversion", "Rejection")
set.seed(20261021)
start <- proc.time()[["elapsed"]]
prediction <- class::knn(train=train[features], test=test[features],
                         cl=factor(train$label, levels=rules),
                         k=1, l=0, prob=TRUE, use.all=TRUE)
elapsed <- proc.time()[["elapsed"]] - start
stopifnot(!anyNA(prediction))
write.csv(data.frame(name=test$name, prediction=as.character(prediction),
                    winning_vote_fraction=attr(prediction, "prob")), args[3], row.names=FALSE)
writeLines(c(paste("R:", R.version.string), paste("class:", packageVersion("class")),
             paste("RNG:", paste(RNGkind(), collapse=", ")), "seed: 20261021",
             "k: 1; l: 0; use.all: TRUE; distance: Euclidean; no additional scaling",
             "All boundary-distance neighbors vote; equal class votes break randomly in class::knn.",
             paste("prediction_elapsed_seconds:", elapsed), capture.output(sessionInfo())), args[4])
