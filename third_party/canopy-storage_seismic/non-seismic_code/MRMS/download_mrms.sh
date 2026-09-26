#!/bin/bash
# Download MRMS data for a date range, for one or both products this
# pipeline needs (reflectivity for rainfall detection/fitting, hourly QPE
# for the precip-rate plots and storage-capacity integration).
#
# Usage: ./download_mrms.sh YYYYMMDD YYYYMMDD [PRODUCT]
#   PRODUCT: REFLECTIVITY | QPE | ALL   (default: ALL -- downloads both)
#
# Examples:
#   ./download_mrms.sh 20250701 20250731            # both products
#   ./download_mrms.sh 20250701 20250731 REFLECTIVITY
#   ./download_mrms.sh 20250701 20250731 QPE

S3_BUCKET="s3://noaa-mrms-pds/CONUS"

START=$1
END=$2
PRODUCT_KEY=${3:-ALL}

if [ -z "$START" ] || [ -z "$END" ]; then
    echo "Usage: $0 YYYYMMDD YYYYMMDD [REFLECTIVITY|QPE|ALL]"
    exit 1
fi

download_product() {
    local product_key=$1
    local product local_dir

    case "$product_key" in
        REFLECTIVITY)
            product="MergedReflectivityQComposite_00.50"
            local_dir="../../output_non-seismic_code/MRMS/MergedReflectivityQComposite/"
            ;;
        QPE)
            product="MultiSensor_QPE_01H_Pass2_00.00"
            local_dir="../../output_non-seismic_code/MRMS/MultiSensor_QPE_01H_Pass2/"
            ;;
        *)
            echo "Unknown product: $product_key (expected REFLECTIVITY or QPE)"
            exit 1
            ;;
    esac

    echo "=== $product_key ($product) -> $local_dir ==="
    local current=$START
    while [ "$current" -le "$END" ]; do
        echo "Downloading $current..."
        aws s3 cp "$S3_BUCKET/$product/$current/" "$local_dir/$current/" \
            --recursive --no-sign-request
        # advance by one day
        current=$(date -d "$current + 1 day" +%Y%m%d 2>/dev/null || \
                  date -j -v+1d -f "%Y%m%d" "$current" +%Y%m%d)
    done
}

case "$PRODUCT_KEY" in
    ALL)
        download_product REFLECTIVITY
        download_product QPE
        ;;
    REFLECTIVITY|QPE)
        download_product "$PRODUCT_KEY"
        ;;
    *)
        echo "Unknown product: $PRODUCT_KEY (expected REFLECTIVITY, QPE, or ALL)"
        exit 1
        ;;
esac

echo "Done."
