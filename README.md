# Backup-All
 
Backup-All is a collection of scripts and configuration files for performing backups.

## Features

- Simple and lightweight backup script.
- Customizable configuration using JSON format.
- MIT licensed.

## Usage

1. Download the latest release from the [Releases](../../releases) page.
2. Extract the contents of the release package.
3. Edit the `config.json` file to specify your backup settings.
4. Run the `backup.bin` script to perform the backup:

    ```bash
    backup.bin
    # config.json should be in the same directory as backup.bin
    ```

## Configuration

The `config.json` file contains settings for specifying the source and destination directories for your backups, as well as any additional options you may want to configure.

Example `config.json`:

```json
{
    "settings": [
        {
            "backup_root": "/path/to/backups",
            "backup_days": "7"
        }
    ],
    "tasks": [
        {
            "type": "mongodb"| "mysql" | "folder"|"volume",
            "docker":{
                "is-docker": true|false,
                "container_name": "container_name",
            }
            "host": "hostname",
            "port": "port",
            "username": "username",
            "password": "password",
            "database": "database",
            "path": "/path/to/backup",
            "volume_name": "volume_name",
        }
    ]
}
```

setup config.json with the example in release package

You can customize these settings according to your specific backup requirements.

## Download Latest Release

You can download the latest release from the Releases page. Both the main program (backup.bin) 
and the configuration file (config.json) are included in the release package.

## License

Backup-All is licensed under the MIT License. See the LICENSE file for details.