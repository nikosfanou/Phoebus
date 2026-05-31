#!/bin/bash

# Install helpers
install_deb() {
    local file=$1
    echo "Installing DEB package: $file"
    sudo dpkg -i "$file"
    sudo apt-get install -f -y
}

extract_zip() {
    local file=$1
    local path=$2
    echo "Extracting ZIP archive: $file"
    unzip -oq "$file" -d "$path"
}

extract_tar_gz() {
    local file=$1
    local path=$2
    echo "Extracting TAR.GZ archive: $file"
    tar -xzf "$file" -C "$path" --overwrite
}

extract_tar_xz() {
    local file=$1
    local path=$2
    echo "Extracting TAR.XZ archive: $file"
    tar -xJf "$file" -C "$path" --overwrite
}

extract_tar_bz2() {
    local file=$1
    local path=$2
    echo "Extracting TAR.BZ2 archive: $file"
    tar -xjf "$file" -C "$path" --overwrite
}

# Version helpers (Chromium browsers)
get_installed_version() {

    local binary=$1
    local browser=$2

    if [ ! -x "$binary" ]; then
        echo ""
        return
    fi

    # Same parsing for all Chromium browsers
    version=$("$binary" --version 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+)+' | head -n1)

    # Brave adds Chromium major in front
    if [ "$browser" = "Brave" ]; then
        version=$(echo "$version" | cut -d'.' -f2-)
    fi

    echo "$version"
}

chromium_browser_installed() {

    local browser=$1
    local expected=$2

    case "$browser" in
        Chrome) binary="/usr/bin/google-chrome" ;;
        Opera) binary="/usr/bin/opera" ;;
        Brave) binary="/usr/bin/brave-browser" ;;
        Edge) binary="/usr/bin/microsoft-edge" ;;
        *) return 1 ;;
    esac

    installed=$(get_installed_version "$binary" "$browser")

    if [ -z "$installed" ]; then
        return 1
    fi

    if [[ "$installed" == "$expected"* ]]; then
        return 0
    fi

    return 1
}

# Driver detection
driver_exists() {

    local browser=$1
    local path=$2

    case "$browser" in
        Opera)
            [ -f "$path/operadriver_linux64/operadriver" ] && return 0
            ;;
        Chrome|Brave)
            [ -f "$path/chromedriver-linux64/chromedriver" ] && return 0
            ;;
        Edge)
            [ -f "$path/msedgedriver" ] && return 0
            ;;
    esac

    return 1
}

main() {

    eval set -- "$OPTIONS"

    DIR="./archive"
    declare -A BROWSERS

    while true; do
    case "$1" in
        -B|--Brave) BROWSERS["Brave"]="$2"; shift 2 ;;
        -C|--Chrome) BROWSERS["Chrome"]="$2"; shift 2 ;;
        -E|--Edge) BROWSERS["Edge"]="$2"; shift 2 ;;
        -F|--Firefox) BROWSERS["Firefox"]="$2"; shift 2 ;;
        -O|--Opera) BROWSERS["Opera"]="$2"; shift 2 ;;
        -T|--Tor) BROWSERS["Tor"]="$2"; shift 2 ;;
        -W|--WebKit) BROWSERS["WebKit"]="$2"; shift 2 ;;
        --) shift; break ;;
        *) echo "Invalid option: $1"; return 1 ;;
    esac
    done

    for browser in "${!BROWSERS[@]}"; do

        version=${BROWSERS[$browser]}
        echo
        echo "Installing $browser version $version..."

        path="$DIR/$browser/$version"

        if [ ! -d "$path" ]; then
            echo "Directory $path does not exist."
            return 1
        fi

        # WebKit
        if [ "$browser" = "WebKit" ]; then
            echo "Skipping WebKit automatic installation."
            continue
        fi

        # Chromium browsers
        skip_browser_install=false

        if [[ "$browser" == "Chrome" || "$browser" == "Opera" || "$browser" == "Brave" || "$browser" == "Edge" ]]; then

            if chromium_browser_installed "$browser" "$version"; then
                echo "$browser version $version already installed."
                skip_browser_install=true
            fi
        fi

        # Install / Extract
        for file in "$path"/*; do

            [ -f "$file" ] || continue

            case "$file" in

                *.deb)

                    if [ "$skip_browser_install" = false ]; then
                        install_deb "$file"
                    else
                        echo "Skipping DEB install for $browser"
                    fi
                    ;;

                *.zip)

                    if driver_exists "$browser" "$path"; then
                        echo "Driver already extracted for $browser."
                    else
                        extract_zip "$file" "$path"
                    fi
                    ;;

                *.tar.gz)

                    extract_tar_gz "$file" "$path"
                    ;;

                *.tar.xz)

                    extract_tar_xz "$file" "$path"
                    ;;

                *.tar.bz2)

                    extract_tar_bz2 "$file" "$path"
                    ;;

                *)

                    echo "Skipping unsupported file ($file)"
                    ;;

            esac

        done

    done
}

OPTIONS=$(getopt -o B:C:E:F:O:T:W: --long Brave:,Chrome:,Edge:,Firefox:,Opera:,Tor:,WebKit: -- "$@")

main

if [ $? -ne 0 ]; then
    echo "Browsers installation failed."
    exit 1
fi

echo "Browsers installation completed successfully."
exit 0