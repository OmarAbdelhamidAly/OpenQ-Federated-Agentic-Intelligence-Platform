<#
.SYNOPSIS
Phased Docker Build Script for OpenQ

.DESCRIPTION
This script builds the OpenQ Docker Compose stack in 4 logical tiers to prevent
system resource exhaustion (CPU/Memory/Network crashes). It clears unused Docker
builder cache between tiers to save disk space.

.EXAMPLE
.\build_phased.ps1
#>

$ErrorActionPreference = "Stop"

# Define the build tiers based on docker-compose.yml services
$Tiers = @(
    @{
        Name = "Tier 1: Data & Observability Layer"
        Services = "postgres redis qdrant neo4j mongodb prometheus grafana flower adminer redis-exporter postgres-exporter cadvisor node-exporter"
    },
    @{
        Name = "Tier 2: Core APIs & Frontend"
        Services = "api corporate frontend"
    },
    @{
        Name = "Tier 3: Standard Workers & Governance"
        Services = "governance exporter worker-json worker-sql"
    },
    @{
        Name = "Tier 4: Heavy AI Workers"
        Services = "worker-code worker-pdf-indexing worker-pdf-analysis worker-audio worker-nexus worker-vision"
    }
)

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🚀 OpenQ Phased Docker Build System 🚀" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "This script will build 26+ services in 4 tiers."
Write-Host "Press Ctrl+C at any time to abort."
Write-Host "---------------------------------------------"

foreach ($tier in $Tiers) {
    Write-Host "`n>>> Starting $($tier.Name) <<<" -ForegroundColor Yellow
    Write-Host "Services: $($tier.Services)" -ForegroundColor DarkGray
    
    # Run docker compose build for the specific tier
    $servicesArray = $tier.Services -split " "
    
    # Execute the build
    $buildCmd = "docker compose build $servicesArray"
    Write-Host "Executing: $buildCmd" -ForegroundColor DarkGray
    
    try {
        docker compose build $servicesArray
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Build failed for tier: $($tier.Name)"
            exit $LASTEXITCODE
        }
    } catch {
        Write-Error "Exception occurred during build: $_"
        exit 1
    }

    Write-Host "✅ $($tier.Name) built successfully!" -ForegroundColor Green
    
    # Free up space by pruning dangling images and build cache
    Write-Host "🧹 Cleaning up Docker build cache to free memory..." -ForegroundColor Cyan
    docker builder prune -f
    
    # Ask to continue if not the last tier
    if ($tier.Name -ne $Tiers[-1].Name) {
        $choice = Read-Host "Do you want to proceed to the next tier? (Y/n)"
        if ($choice -eq 'n' -or $choice -eq 'N') {
            Write-Host "Build paused. You can resume later." -ForegroundColor Yellow
            exit 0
        }
    }
}

Write-Host "`n🎉 All 4 Tiers built successfully! 🎉" -ForegroundColor Green
Write-Host "You can now start the stack using: docker compose up -d" -ForegroundColor Cyan
