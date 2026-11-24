param(
    [ValidateSet('build','test','html','wiki','join','index','search','compare','verify-real')]
    [string]$Step = 'search',
    [string]$Query = '',
    [int]$YearFrom = 0,
    [int]$YearTo = 0,
    [string]$Tag = '',
    [string]$Author = ''
)
$ErrorActionPreference = 'Stop'
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'

function Invoke-App([string[]]$AppArgs) {
    & docker compose -f $composeFile run --rm app @AppArgs
    if ($LASTEXITCODE -ne 0) { throw "The command failed (exit $LASTEXITCODE)." }
}

$sparkArgs = @('spark-submit','--master','local[4]','--driver-memory','4g','spark_job.py')
switch ($Step) {
    'build' {
        & docker compose -f $composeFile build
        if ($LASTEXITCODE -ne 0) { throw 'Docker build failed.' }
    }
    'test' { Invoke-App @('python','verify.py') }
    'html' { Invoke-App ($sparkArgs + @('html','--output','data/books')) }
    'wiki' { Invoke-App ($sparkArgs + @('wiki','--dump','/input/wiki.xml','--output','data/wiki')) }
    'join' {
        Invoke-App ($sparkArgs + @('join','--output','data/enriched'))
        Invoke-App @('python','summarize.py')
    }
    'index' {
        $originalArgs = @()
        if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'input/old/knihy.csv')) {
            $originalArgs = @('--original-csv','/input/old/knihy.csv')
        }
        Invoke-App (@('python','lucene_index.py','--input','data/enriched','--index','indexes/plain','--plain') + $originalArgs)
        Invoke-App (@('python','lucene_index.py','--input','data/enriched','--index','indexes/enriched') + $originalArgs)
    }
    'search' {
        $searchArgs = @('python','search.py')
        # An environment variable preserves phrase quotes through PowerShell 5 and Docker.
        if ($Query) { $env:VINF_QUERY = $Query; $searchArgs += '--query-env' }
        elseif ($YearFrom -or $YearTo -or $Tag -or $Author) { $searchArgs += '*:*' }
        if ($YearFrom) { $searchArgs += @('--year-from', "$YearFrom") }
        if ($YearTo) { $searchArgs += @('--year-to', "$YearTo") }
        if ($Tag) { $searchArgs += @('--tag', $Tag) }
        if ($Author) { $searchArgs += @('--author', $Author) }
        Invoke-App $searchArgs
    }
    'compare' { Invoke-App @('python','compare.py') }
    'verify-real' { Invoke-App @('python','verify_real.py','--indexes') }
}
