# JRuby workload: files, directories, JSON, regex, threads, a local TCP server and client, Java
# integration, Dir/FileUtils, Zlib. Prints "OPS ok=<n> fail=<n>" (last line).
require 'json'; require 'fileutils'; require 'tmpdir'; require 'socket'; require 'zlib'
ok = 0; fail = 0; errs = []
step = lambda { |n, &b| begin; b.call; ok += 1; rescue Exception => e; fail += 1; errs << "#{n}: #{e}"; end }
base = Dir.mktmpdir('wl')
5.times do |r|
  d = File.join(base, "d#{r}")
  step.call('files') { FileUtils.mkdir_p(d); 200.times { |i| File.write(File.join(d, "f#{i}.txt"), "line #{i}\n" * 50) }; raise 'n' unless Dir.children(d).size == 200 }
  step.call('read+regex') { n = 0; Dir.glob("#{d}/*.txt") { |f| n += File.read(f).scan(/line \d+/).size }; raise 'n' unless n == 10000 }
  step.call('rename+chmod') { File.rename(File.join(d, 'f0.txt'), File.join(d, 'g.txt')); File.chmod(0600, File.join(d, 'g.txt')) }
  step.call('json') { s = JSON.generate((0...2000).map { |i| { id: i, name: "n#{i}", tags: %w[a b] } }); raise 'n' unless JSON.parse(s).size == 2000 }
  step.call('zlib') { z = Zlib::Deflate.deflate('x' * 100000); raise 'n' unless Zlib::Inflate.inflate(z).size == 100000 }
  step.call('threads') { 16.times.map { Thread.new { x = 0; 20000.times { |i| x += i }; x } }.each(&:join) }
  step.call('tcp') {
    srv = TCPServer.new('127.0.0.1', 0); port = srv.addr[1]
    t = Thread.new { 100.times { c = srv.accept; c.write(c.gets); c.close } }
    100.times { |i| s = TCPSocket.new('127.0.0.1', port); s.puts("m#{i}"); raise 'echo' unless s.gets.strip == "m#{i}"; s.close }
    t.join; srv.close
  }
  step.call('java') { l = java.util.ArrayList.new; 1000.times { |i| l.add(i) }; raise 'n' unless l.size == 1000 }
  step.call('rm tree') { FileUtils.rm_rf(d); raise 'left' if File.exist?(d) }
end
step.call('cleanup') { FileUtils.remove_entry(base) }
errs.each { |e| $stderr.puts e }
puts "OPS ok=#{ok} fail=#{fail}"
