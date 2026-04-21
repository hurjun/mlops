/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone: Docker 이미지를 최소 크기로 만들기 위한 설정
  // Dockerfile에서 .next/standalone 폴더만 복사하면 실행 가능한 상태가 됨
  output: "standalone",
};

module.exports = nextConfig;
