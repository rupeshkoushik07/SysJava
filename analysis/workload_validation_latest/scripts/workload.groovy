// Groovy workload: files, directories, JSON, XML, regex, collections, threads, a local HTTP server and
// client, zip, process exit code. Prints "OPS ok=<n> fail=<n>" (last line).
import groovy.json.*
import java.util.concurrent.*
import java.util.zip.*
import com.sun.net.httpserver.HttpServer
def ok = 0, fail = 0, errs = []
def step = { String n, Closure c -> try { c(); ok++ } catch (Throwable e) { fail++; errs << "$n: $e" } }
def base = File.createTempDir("wl", "")
for (r in 0..<5) {
  step("files") { def d = new File(base, "d$r"); d.mkdirs(); (0..<200).each { new File(d, "f${it}.txt").text = "line $it\n" * 50 }; assert d.listFiles().size() == 200 }
  step("read+regex") { def n = 0; new File(base, "d$r").eachFile { f -> n += (f.text =~ /line \d+/).size() }; assert n == 10000 }
  step("rename") { new File(base, "d${r}/f0.txt").renameTo(new File(base, "d${r}/renamed.txt")) || { throw new RuntimeException("rename") }() }
  step("json") { def j = JsonOutput.toJson((0..<2000).collect { [id: it, name: "n$it", tags: ["a", "b"]] }); assert new JsonSlurper().parseText(j).size() == 2000 }
  step("xml") { def w = new StringWriter(); new groovy.xml.MarkupBuilder(w).root { (0..<500).each { item(id: it, "v$it") } }; assert new groovy.xml.XmlSlurper().parseText(w.toString()).item.size() == 500 }
  step("zip") { def z = new File(base, "a${r}.zip"); new ZipOutputStream(new FileOutputStream(z)).withCloseable { zo -> new File(base, "d$r").eachFile { f -> zo.putNextEntry(new ZipEntry(f.name)); zo << f.bytes; zo.closeEntry() } }; assert new ZipFile(z).size() == 200 }
  step("threads") { def ex = Executors.newFixedThreadPool(8); def fs = (0..<64).collect { i -> ex.submit({ (0..<20000).sum() } as Callable) }; fs*.get(); ex.shutdown(); ex.awaitTermination(30, TimeUnit.SECONDS) }
  step("http") {
    def srv = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0)
    srv.createContext("/") { ex -> def b = "hello".bytes; ex.sendResponseHeaders(200, b.length); ex.responseBody.withCloseable { it << b } }
    srv.start(); def port = srv.address.port
    (0..<200).each { assert new URL("http://127.0.0.1:$port/x$it").text == "hello" }
    srv.stop(0)
  }
  step("delete tree") { assert new File(base, "d$r").deleteDir() }
}
step("cleanup") { assert base.deleteDir() }
errs.each { System.err.println(it) }
println "OPS ok=$ok fail=$fail"
