import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description='使用 JDK 和 Android SDK 构建本地调试 APK。')
    parser.add_argument('--sdk', type=Path, default=os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT'))
    parser.add_argument('--java-home', type=Path, default=os.environ.get('JAVA_HOME'))
    parser.add_argument('--build-tools', default='35.0.0')
    args = parser.parse_args()
    if args.sdk is None:
        parser.error('请设置 ANDROID_HOME 或使用 --sdk 指定 Android SDK。')
    sdk = args.sdk.resolve()
    java_bin = args.java_home.resolve() / 'bin' if args.java_home else None

    def java_tool(name):
        executable = str(java_bin / (name + ('.exe' if os.name == 'nt' else ''))) if java_bin else shutil.which(name)
        if not executable or not Path(executable).is_file():
            parser.error(f'找不到 {name}，请使用 --java-home 指定 JDK（建议17或21）。')
        return executable

    build_tools = sdk / 'build-tools' / args.build_tools
    android_jar = sdk / 'platforms' / 'android-35' / 'android.jar'
    for required in (android_jar, build_tools / 'lib' / 'd8.jar', build_tools / 'lib' / 'apksigner.jar'):
        if not required.is_file():
            parser.error(f'缺少 SDK 组件：{required}')
    output = ROOT / 'build' / 'android'
    # 每次编译使用独立目录，防止残留的类文件进入 APK。
    output.mkdir(parents=True, exist_ok=True)
    task_env = dict(os.environ)
    task_env.update(TEMP=str(output), TMP=str(output), TMPDIR=str(output))

    def run(*command):
        subprocess.run([str(part) for part in command], check=True, cwd=ROOT, env=task_env)

    with tempfile.TemporaryDirectory(prefix='compile-', dir=output) as temporary:
        work = Path(temporary)
        classes, dex = work / 'classes', work / 'dex'
        classes.mkdir()
        dex.mkdir()
        manifest = ET.parse(ROOT / 'android' / 'app' / 'src' / 'main' / 'AndroidManifest.xml')
        manifest.getroot().set('package', 'org.campusroute.android')
        ET.register_namespace('android', 'http://schemas.android.com/apk/res/android')
        manifest_path = work / 'AndroidManifest.xml'
        manifest.write(manifest_path, encoding='utf-8', xml_declaration=True)
        unsigned, aligned = work / 'unsigned.apk', work / 'aligned.apk'
        suffix = '.exe' if os.name == 'nt' else ''
        resources = work / 'resources.zip'
        run(build_tools / ('aapt2' + suffix), 'compile', '--dir',
            ROOT / 'android' / 'app' / 'src' / 'main' / 'res', '-o', resources)
        run(build_tools / ('aapt2' + suffix), 'link', '-I', android_jar,
            '--manifest', manifest_path, '-o', unsigned, resources)
        sources = sorted((ROOT / 'android' / 'app' / 'src' / 'main' / 'java').rglob('*.java'))
        run(java_tool('javac'), '--release', '8', '-encoding', 'UTF-8', '-classpath', android_jar,
            '-d', classes, *sources)
        class_jar = work / 'classes.jar'
        with zipfile.ZipFile(class_jar, 'w') as archive:
            for path in classes.rglob('*.class'):
                archive.write(path, path.relative_to(classes).as_posix())
        run(java_tool('java'), '-cp', build_tools / 'lib' / 'd8.jar', 'com.android.tools.r8.D8',
            '--lib', android_jar, '--min-api', '29', '--output', dex, class_jar)
        with zipfile.ZipFile(unsigned, 'a') as archive:
            for path in dex.glob('*.dex'):
                archive.write(path, path.name)
        run(build_tools / ('zipalign' + suffix), '-f', '-p', '4', unsigned, aligned)
        keystore = output / 'debug.keystore'
        if not keystore.exists():
            run(java_tool('keytool'), '-genkeypair', '-keystore', keystore, '-storepass', 'android',
                '-keypass', 'android', '-alias', 'androiddebugkey', '-keyalg', 'RSA', '-keysize', '2048',
                '-validity', '10000', '-dname', 'CN=CampusRoute Debug', '-storetype', 'JKS', '-noprompt')
        apk = output / 'CampusRoute-debug.apk'
        signer = [java_tool('java'), '-jar', build_tools / 'lib' / 'apksigner.jar']
        run(*signer, 'sign', '--ks', keystore, '--ks-key-alias', 'androiddebugkey',
            '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', apk, aligned)
        run(*signer, 'verify', '--verbose', apk)
        print(f'\nAPK: {apk}')
        print('这是本地调试签名。保留 build/android/debug.keystore，后续构建才能覆盖安装。')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f'构建失败：命令退出码 {error.returncode}', file=sys.stderr)
        raise SystemExit(1)
