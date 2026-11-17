# Manual validation sample (seed 20261116, 20 per stratum)

Population: resolved mappings behind Table II (JDK 8) and Table III (latest). Columns: Java side, chosen native function and library, the evidence to check, and a pre-check verdict to confirm.

| Stratum | Population | JDK 8 | Latest | Images | Sampled | Sampled images | correct | correct (library note) | correct (version note) | unverifiable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 explicit registration | 7,790 | 2,544 | 5,246 | 20 | 20 | 20 | 20 | 0 | 0 | 0 |
| 2 name heuristic / bridge | 152 | 28 | 124 | 10 | 20 | 10 | 20 | 0 | 0 | 0 |
| 3 JNA | 110 | 41 | 69 | 6 | 20 | 6 | 9 | 0 | 0 | 11 |
| 4 JNR-FFI | 67 | 33 | 34 | 3 | 20 | 3 | 13 | 0 | 0 | 7 |
| 5 FFM | 206 | 0 | 206 | 2 | 20 | 2 | 12 | 6 | 0 | 2 |
| 6 manual / supplied library | 943 | 411 | 532 | 20 | 20 | 20 | 18 | 0 | 2 | 0 |
| 7 control: JNI symbol lookup | 21,058 | 8,634 | 12,424 | 20 | 20 | 20 | 20 | 0 | 0 | 0 |

## 1. explicit registration

**S1-01** storm_2.8.8 (latest) `[JNI_DYNAMIC]` — **correct**: decoded JNINativeMethod entry names getTcpUserTimeout and points to netty_epoll_linuxsocket_getTcpUserTimeout  
Java: `org.apache.storm.shade.io.netty.channel.epoll.LinuxSocket.getTcpUserTimeout`  
Native: `netty_epoll_linuxsocket_getTcpUserTimeout` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/storm_2.8.8/Dataset/LIBS_storm_2.8.8/liborg_apache_storm_shade_netty_transport_native_epoll_x86_64.so` (sha256 7d9fbdf2b59e92c3)  
- nm: 0000000000007730 t netty_epoll_linuxsocket_getTcpUserTimeout (local, not exported)  
- RegisterNatives entry: liborg_apache_storm_shade_netty_transport_native_epoll_x86_64.so vaddr 0x151b0 (file offset 0x141b0): {"getTcpUserTimeout", "(I)I", 0x7730 (netty_epoll_linuxsocket_getTcpUserTimeout)}

**S1-02** solr_10.0.0 (latest) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names putChar and points to Unsafe_PutChar  
Java: `jdk.internal.misc.Unsafe.putChar`  
Native: `Unsafe_PutChar` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/solr_10.0.0/Dataset/LIBS_solr_10.0.0/JDK25_LIBS/server/libjvm.so` (sha256 acae4f2568239570)  
- nm: 0000000001236580 t Unsafe_PutChar (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|jdk.internal.misc.Unsafe.putChar|(Ljava/lang/Object;JC)V|Unsafe_PutChar|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x1781cd0 (file offset 0x1781cd0): {"putChar", "(Ljava/lang/Object;JC)V", 0x1236580 (Unsafe_PutChar)}

**S1-03** jruby_9.4.2.0-jdk8-buster (jdk8) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names getTicksFrequency and points to jfr_elapsed_frequency  
Java: `jdk.jfr.internal.JVM.getTicksFrequency`  
Native: `jfr_elapsed_frequency` in `~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset/LIBS_jruby_9.4.2.0-jdk8-buster/JDK8_LIBS/amd64/server/libjvm.so` (sha256 da71c35e28da3257)  
- nm: 00000000006c73a0 t jfr_elapsed_frequency (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|jdk.jfr.internal.JVM.getTicksFrequency|()J|jfr_elapsed_frequency|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x100e368 (file offset 0xe0e368): {"getTicksFrequency", "()J", 0x6c73a0 (jfr_elapsed_frequency)}

**S1-04** tomcat_11.0.22 (latest) `[JVM]` — **correct**: decoded JNINativeMethod entry names getNextThreadIdOffset and points to JVM_GetNextThreadIdOffset  
Java: `java.lang.Thread.getNextThreadIdOffset`  
Native: `JVM_GetNextThreadIdOffset` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/JDK25_LIBS/server/libjvm.so` (sha256 5dffa2b4bcdff59a)  
- nm -D: 0000000000b18380 T JVM_GetNextThreadIdOffset  
- jvm_dynamic_mapping.txt: libjava.so|java.lang.Thread.getNextThreadIdOffset|()J|JVM_GetNextThreadIdOffset|BIN_SCAN  
- RegisterNatives entry: libjava.so vaddr 0x22448 (file offset 0x22448): {"getNextThreadIdOffset", "()J", JVM_GetNextThreadIdOffset}

**S1-05** zookeeper_3.9.5 (latest) `[JNI_DYNAMIC]` — **correct**: decoded JNINativeMethod entry names upRef and points to netty_internal_tcnative_SSLCredential_upRef  
Java: `io.netty.internal.tcnative.SSLCredential.upRef`  
Native: `netty_internal_tcnative_SSLCredential_upRef` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libnetty_tcnative_linux_x86_64.so` (sha256 d1a459fc041d002e)  
- nm: 000000000002f870 t netty_internal_tcnative_SSLCredential_upRef (local, not exported)  
- jni_dynamic_bindings.txt: libnetty_tcnative_linux_x86_64.so|io.netty.internal.tcnative.SSLCredential.upRef|(J)V|netty_internal_tcnative_SSLCredential_upRef|HIGH_CONF  
- RegisterNatives entry: libnetty_tcnative_linux_x86_64.so vaddr 0x26d3d8 (file offset 0x26c3d8): {"upRef", "(J)V", 0x2f870 (netty_internal_tcnative_SSLCredential_upRef)}

**S1-06** elasticsearch_7.1.0 (latest) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names putInt and points to Unsafe_PutInt  
Java: `jdk.internal.misc.Unsafe.putInt`  
Native: `Unsafe_PutInt` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/elasticsearch_7.1.0/Dataset/LIBS_elasticsearch_7.1.0/JDK12_LIBS/server/libjvm.so` (sha256 91223359e6796b47)  
- nm: 0000000000e017f0 t Unsafe_PutInt (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|jdk.internal.misc.Unsafe.putInt|(Ljava/lang/Object;JI)V|Unsafe_PutInt|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x1444670 (file offset 0x1244670): {"putInt", "(Ljava/lang/Object;JI)V", 0xe017f0 (Unsafe_PutInt)}

**S1-07** jetty_9.4.51-jdk8-buster (jdk8) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names defineClass and points to Unsafe_DefineClass0  
Java: `sun.misc.Unsafe.defineClass`  
Native: `Unsafe_DefineClass0` in `~/Tutorial/EchoTrace/Final_results_JDK8/jetty_9.4.51-jdk8-buster/Dataset/LIBS_jetty_9.4.51-jdk8-buster/JDK8_LIBS/amd64/server/libjvm.so` (sha256 da71c35e28da3257)  
- nm: 0000000000b050b0 t Unsafe_DefineClass0 (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|sun.misc.Unsafe.defineClass|(Ljava/lang/String;[BII)Ljava/lang/Class;|Unsafe_DefineClass0|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x1013ea8 (file offset 0xe13ea8): {"defineClass", "(Ljava/lang/String;[BII)Ljava/lang/Class;", 0xb050b0 (Unsafe_DefineClass0)}

**S1-08** groovy_5.0.6 (latest) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names getDoubleVolatile and points to Unsafe_GetDoubleVolatile  
Java: `jdk.internal.misc.Unsafe.getDoubleVolatile`  
Native: `Unsafe_GetDoubleVolatile` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/groovy_5.0.6/Dataset/LIBS_groovy_5.0.6/JDK21_LIBS/server/libjvm.so` (sha256 f59cef8ff26a4558)  
- nm: 0000000000fd1b70 t Unsafe_GetDoubleVolatile (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|jdk.internal.misc.Unsafe.getDoubleVolatile|(Ljava/lang/Object;J)D|Unsafe_GetDoubleVolatile|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x151eec8 (file offset 0x151dec8): {"getDoubleVolatile", "(Ljava/lang/Object;J)D", 0xfd1b70 (Unsafe_GetDoubleVolatile)}

**S1-09** zookeeper_3.4.14-jdk8-buster (jdk8) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names putDouble and points to Unsafe_SetDouble  
Java: `sun.misc.Unsafe.putDouble`  
Native: `Unsafe_SetDouble` in `~/Tutorial/EchoTrace/Final_results_JDK8/zookeeper_3.4.14-jdk8-buster/Dataset/LIBS_zookeeper_3.4.14-jdk8-buster/JDK8_LIBS/amd64/server/libjvm.so` (sha256 da71c35e28da3257)  
- nm: 0000000000b06e80 t Unsafe_SetDouble (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|sun.misc.Unsafe.putDouble|(Ljava/lang/Object;JD)V|Unsafe_SetDouble|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x1013498 (file offset 0xe13498): {"putDouble", "(Ljava/lang/Object;JD)V", 0xb06e80 (Unsafe_SetDouble)}

**S1-10** groovy_4.0.0-jdk8-buster (jdk8) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names putShort and points to Unsafe_SetShort140  
Java: `sun.misc.Unsafe.putShort`  
Native: `Unsafe_SetShort140` in `~/Tutorial/EchoTrace/Final_results_JDK8/groovy_4.0.0-jdk8-buster/Dataset/LIBS_groovy_4.0.0-jdk8-buster/JDK8_LIBS/amd64/server/libjvm.so` (sha256 da71c35e28da3257)  
- nm: 0000000000b0eab0 t Unsafe_SetShort140 (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|sun.misc.Unsafe.putShort|(Ljava/lang/Object;IS)V|Unsafe_SetShort140|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x1014ca8 (file offset 0xe14ca8): {"putShort", "(Ljava/lang/Object;IS)V", 0xb0eab0 (Unsafe_SetShort140)}

**S1-11** orientdb_3.2.19-jdk8-buster (jdk8) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names putLongVolatile and points to Unsafe_SetLongVolatile  
Java: `sun.misc.Unsafe.putLongVolatile`  
Native: `Unsafe_SetLongVolatile` in `~/Tutorial/EchoTrace/Final_results_JDK8/orientdb_3.2.19-jdk8-buster/Dataset/LIBS_orientdb_3.2.19-jdk8-buster/JDK8_LIBS/amd64/server/libjvm.so` (sha256 da71c35e28da3257)  
- nm: 0000000000b07590 t Unsafe_SetLongVolatile (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|sun.misc.Unsafe.putLongVolatile|(Ljava/lang/Object;JJ)V|Unsafe_SetLongVolatile|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x1013408 (file offset 0xe13408): {"putLongVolatile", "(Ljava/lang/Object;JJ)V", 0xb07590 (Unsafe_SetLongVolatile)}

**S1-12** storm_2.4.0-jdk8-buster (jdk8) `[JNI_DYNAMIC]` — **correct**: decoded JNINativeMethod entry names splice0 and points to netty_epoll_native_splice0  
Java: `org.apache.storm.shade.io.netty.channel.epoll.Native.splice0`  
Native: `netty_epoll_native_splice0` in `~/Tutorial/EchoTrace/Final_results_JDK8/storm_2.4.0-jdk8-buster/Dataset/LIBS_storm_2.4.0-jdk8-buster/libnetty_transport_native_epoll_x86_64.so` (sha256 4059ae0ec61e0707)  
- nm: 0000000000003d10 t netty_epoll_native_splice0 (local, not exported)  
- RegisterNatives entry: libnetty_transport_native_epoll_x86_64.so vaddr 0x20c800 (file offset 0xc800): {"splice0", "(IJIJJ)I", 0x3d10 (netty_epoll_native_splice0)}

**S1-13** elasticsearch_7.5.2-jdk8-buster (jdk8) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names getByte and points to Unsafe_GetNativeByte  
Java: `sun.misc.Unsafe.getByte`  
Native: `Unsafe_GetNativeByte` in `~/Tutorial/EchoTrace/Final_results_JDK8/elasticsearch_7.5.2-jdk8-buster/Dataset/LIBS_elasticsearch_7.5.2-jdk8-buster/JDK8_LIBS/amd64/server/libjvm.so` (sha256 da71c35e28da3257)  
- nm: 0000000000b0aea0 t Unsafe_GetNativeByte (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|sun.misc.Unsafe.getByte|(J)B|Unsafe_GetNativeByte|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x10134e0 (file offset 0xe134e0): {"getByte", "(J)B", 0xb0aea0 (Unsafe_GetNativeByte)}

**S1-14** tomcat_7.0-jdk8-buster (jdk8) `[REGISTERED]` — **correct**: decoded JNINativeMethod entry names putShort and points to Unsafe_SetShort  
Java: `sun.misc.Unsafe.putShort`  
Native: `Unsafe_SetShort` in `~/Tutorial/EchoTrace/Final_results_JDK8/tomcat_7.0-jdk8-buster/Dataset/LIBS_tomcat_7.0-jdk8-buster/JDK8_LIBS/amd64/server/libjvm.so` (sha256 da71c35e28da3257)  
- nm: 0000000000b076f0 t Unsafe_SetShort (local, not exported)  
- jvm_dynamic_mapping.txt: libjvm.so|sun.misc.Unsafe.putShort|(Ljava/lang/Object;JS)V|Unsafe_SetShort|BIN_SCAN  
- RegisterNatives entry: libjvm.so vaddr 0x10132b8 (file offset 0xe132b8): {"putShort", "(Ljava/lang/Object;JS)V", 0xb076f0 (Unsafe_SetShort)}

**S1-15** solr_8.7.0-jdk8-buster (jdk8) `[JVM]` — **correct**: decoded JNINativeMethod entry names getModifiers and points to JVM_GetClassModifiers  
Java: `java.lang.Class.getModifiers`  
Native: `JVM_GetClassModifiers` in `~/Tutorial/EchoTrace/Final_results_JDK8/solr_8.7.0-jdk8-buster/Dataset/LIBS_solr_8.7.0-jdk8-buster/JDK8_LIBS/amd64/server/libjvm.so` (sha256 da71c35e28da3257)  
- nm -D: 0000000000747070 T JVM_GetClassModifiers  
- jvm_dynamic_mapping.txt: libjava.so|java.lang.Class.getModifiers|()I|JVM_GetClassModifiers|BIN_SCAN  
- RegisterNatives entry: libjava.so vaddr 0x229738 (file offset 0x29738): {"getModifiers", "()I", JVM_GetClassModifiers}

**S1-16** orientdb_3.2.53 (latest) `[JVM]` — **correct**: decoded JNINativeMethod entry names getDeclaredMethods0 and points to JVM_GetClassDeclaredMethods  
Java: `java.lang.Class.getDeclaredMethods0`  
Native: `JVM_GetClassDeclaredMethods` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/orientdb_3.2.53/Dataset/LIBS_orientdb_3.2.53/JDK8_LIBS/amd64/server/libjvm.so` (sha256 f065bd82a1aef160)  
- nm -D: 0000000000755de0 T JVM_GetClassDeclaredMethods  
- jvm_dynamic_mapping.txt: libjava.so|java.lang.Class.getDeclaredMethods0|(Z)[Ljava/lang/reflect/Method;|JVM_GetClassDeclaredMethods|BIN_SCAN  
- RegisterNatives entry: libjava.so vaddr 0x229768 (file offset 0x29768): {"getDeclaredMethods0", "(Z)[Ljava/lang/reflect/Method;", JVM_GetClassDeclaredMethods}

**S1-17** jetty_12.1.10 (latest) `[JVM]` — **correct**: decoded JNINativeMethod entry names getDeclaredMethods0 and points to JVM_GetClassDeclaredMethods  
Java: `java.lang.Class.getDeclaredMethods0`  
Native: `JVM_GetClassDeclaredMethods` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jetty_12.1.10/Dataset/LIBS_jetty_12.1.10/JDK25_LIBS/server/libjvm.so` (sha256 5dffa2b4bcdff59a)  
- nm -D: 0000000000b2a890 T JVM_GetClassDeclaredMethods  
- jvm_dynamic_mapping.txt: libjava.so|java.lang.Class.getDeclaredMethods0|(Z)[Ljava/lang/reflect/Method;|JVM_GetClassDeclaredMethods|BIN_SCAN  
- RegisterNatives entry: libjava.so vaddr 0x22098 (file offset 0x22098): {"getDeclaredMethods0", "(Z)[Ljava/lang/reflect/Method;", JVM_GetClassDeclaredMethods}

**S1-18** cassandra_3.0.29-jdk8-buster (jdk8) `[JNI_DYNAMIC]` — **correct**: decoded JNINativeMethod entry names finishConnect and points to netty_unix_socket_finishConnect  
Java: `io.netty.channel.unix.Socket.finishConnect`  
Native: `netty_unix_socket_finishConnect` in `~/Tutorial/EchoTrace/Final_results_JDK8/cassandra_3.0.29-jdk8-buster/Dataset/LIBS_cassandra_3.0.29-jdk8-buster/libnetty-transport-native-epoll.so` (sha256 29f94baa0f2f5b57)  
- nm: 0000000000005920 t netty_unix_socket_finishConnect (local, not exported)  
- jni_dynamic_bindings.txt: libnetty-transport-native-epoll.so|io.netty.channel.unix.Socket.finishConnect|(I)I|netty_unix_socket_finishConnect|HIGH_CONF  
- RegisterNatives entry: libnetty-transport-native-epoll.so vaddr 0x20b1c0 (file offset 0xb1c0): {"finishConnect", "(I)I", 0x5920 (netty_unix_socket_finishConnect)}

**S1-19** cassandra_5.0.8 (latest) `[JNI_DYNAMIC]` — **correct**: decoded JNINativeMethod entry names x509vErrUnhandledCriticalCrlExtension and points to netty_internal_tcnative_NativeStaticallyReferencedJniMethods_x509vErrUnhandledCriticalCrlExtension  
Java: `io.netty.internal.tcnative.NativeStaticallyReferencedJniMethods.x509vErrUnhandledCriticalCrlExtension`  
Native: `netty_internal_tcnative_NativeStaticallyReferencedJniMethods_x509vErrUnhandledCriticalCrlExtension` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/libnetty_tcnative_linux_x86_64.so` (sha256 ec0fe8ed43699c52)  
- nm: 000000000002d390 t netty_internal_tcnative_NativeStaticallyReferencedJniMethods_x509vErrUnhandledCriticalCrlExtension (local, not exported)  
- jni_dynamic_bindings.txt: libnetty_tcnative_linux_x86_64.so|io.netty.internal.tcnative.NativeStaticallyReferencedJniMethods.x509vErrUnhandledCriticalCrlExtension|()I|netty_internal_tcnative_NativeStaticallyReferencedJniMethods_x509vErrUnhandledCriticalCrlExtension|HIGH_CONF  
- RegisterNatives entry: libnetty_tcnative_linux_x86_64.so vaddr 0x23e000 (file offset 0x23d000): {"x509vErrUnhandledCriticalCrlExtension", "()I", 0x2d390 (netty_internal_tcnative_NativeStaticallyReferencedJniMethods_x509vErrUnhandledCriticalCrlExtension)}

**S1-20** jruby_10.1.0.0 (latest) `[JVM]` — **correct**: decoded JNINativeMethod entry names isPrimitive and points to JVM_IsPrimitiveClass  
Java: `java.lang.Class.isPrimitive`  
Native: `JVM_IsPrimitiveClass` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/JDK21_LIBS/server/libjvm.so` (sha256 26d9fefbe1dc56b5)  
- nm -D: 00000000009f4380 T JVM_IsPrimitiveClass  
- jvm_dynamic_mapping.txt: libjava.so|java.lang.Class.isPrimitive|()Z|JVM_IsPrimitiveClass|BIN_SCAN  
- RegisterNatives entry: libjava.so vaddr 0x220e0 (file offset 0x210e0): {"isPrimitive", "()Z", JVM_IsPrimitiveClass}


## 2. name heuristic / bridge

**S2-01** tomcat_11.0.22 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.hashCode`  
Native: `JVM_IHashCode` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/JDK25_LIBS/server/libjvm.so` (sha256 5dffa2b4bcdff59a)  
- nm -D: 0000000000b1aa90 T JVM_IHashCode  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.hashCode -> JVM_IHashCode (libjava registers it; HotSpot export)

**S2-02** groovy_5.0.6 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.hashCode`  
Native: `JVM_IHashCode` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/groovy_5.0.6/Dataset/LIBS_groovy_5.0.6/JDK21_LIBS/server/libjvm.so` (sha256 f59cef8ff26a4558)  
- nm -D: 00000000009f35e0 T JVM_IHashCode  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.hashCode -> JVM_IHashCode (libjava registers it; HotSpot export)

**S2-03** storm_2.4.0-jdk8-buster (jdk8) `[NETTY]` — **correct**: symbol exists and ends with the Java method name; no static table entry  
Java: `io.netty.channel.unix.Socket.recvFromAddress`  
Native: `netty_unix_socket_recvFromAddress` in `~/Tutorial/EchoTrace/Final_results_JDK8/storm_2.4.0-jdk8-buster/Dataset/LIBS_storm_2.4.0-jdk8-buster/libnetty_transport_native_epoll_x86_64.so` (sha256 4059ae0ec61e0707)  
- nm: 0000000000008bb0 t netty_unix_socket_recvFromAddress (local, not exported)  
- rule: Netty symbol naming (netty_<module>_<class>_<method>) for io.netty.channel.unix.Socket.recvFromAddress

**S2-04** cassandra_5.0.8 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.wait`  
Native: `JVM_MonitorWait` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/JDK17_LIBS/server/libjvm.so` (sha256 7d064a0dbf29c8ca)  
- nm -D: 00000000008f9b40 T JVM_MonitorWait  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.wait -> JVM_MonitorWait (libjava registers it; HotSpot export)

**S2-05** solr_10.0.0 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.notifyAll`  
Native: `JVM_MonitorNotifyAll` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/solr_10.0.0/Dataset/LIBS_solr_10.0.0/JDK25_LIBS/server/libjvm.so` (sha256 acae4f2568239570)  
- nm -D: 0000000000b1ae70 T JVM_MonitorNotifyAll  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.notifyAll -> JVM_MonitorNotifyAll (libjava registers it; HotSpot export)

**S2-06** jruby_10.1.0.0 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.hashCode`  
Native: `JVM_IHashCode` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/JDK21_LIBS/server/libjvm.so` (sha256 26d9fefbe1dc56b5)  
- nm -D: 00000000009f35e0 T JVM_IHashCode  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.hashCode -> JVM_IHashCode (libjava registers it; HotSpot export)

**S2-07** storm_2.8.8 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.clone`  
Native: `JVM_Clone` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/storm_2.8.8/Dataset/LIBS_storm_2.8.8/JDK17_LIBS/server/libjvm.so` (sha256 7d064a0dbf29c8ca)  
- nm -D: 00000000008f9ff0 T JVM_Clone  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.clone -> JVM_Clone (libjava registers it; HotSpot export)

**S2-08** zookeeper_3.9.5 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.notify`  
Native: `JVM_MonitorNotify` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/JDK17_LIBS/server/libjvm.so` (sha256 7d064a0dbf29c8ca)  
- nm -D: 00000000008f9db0 T JVM_MonitorNotify  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.notify -> JVM_MonitorNotify (libjava registers it; HotSpot export)

**S2-09** jetty_12.1.10 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.hashCode`  
Native: `JVM_IHashCode` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jetty_12.1.10/Dataset/LIBS_jetty_12.1.10/JDK25_LIBS/server/libjvm.so` (sha256 5dffa2b4bcdff59a)  
- nm -D: 0000000000b1aa90 T JVM_IHashCode  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.hashCode -> JVM_IHashCode (libjava registers it; HotSpot export)

**S2-10** cassandra_3.0.29-jdk8-buster (jdk8) `[DIRECT_LIBC_BRIDGE]` — **correct**: library recorded as an importing library (libjvm.so); function resolves to libc's fcntl in the dependency graph; syscalls unaffected  
Java: `org.apache.cassandra.utils.NativeLibraryLinux.fcntl`  
Native: `fcntl` in `~/Tutorial/EchoTrace/Final_results_JDK8/cassandra_3.0.29-jdk8-buster/Dataset/LIBS_cassandra_3.0.29-jdk8-buster/JDK8_LIBS/amd64/server/libjvm.so` (sha256 da71c35e28da3257)  
- fcntl not defined in libjvm.so  
- rule: JNA direct-mapped native org.apache.cassandra.utils.NativeLibraryLinux.fcntl calls the libc function of the same name  
- libc-2.28.so nm -D: 00000000000ea7b0 W fcntl  
- pipeline SysPart run of libjvm.so: start fcntl resolves to fcntl at 0xea7b0 in libc.so.6

**S2-11** tomcat_11.0.22 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.notifyAll`  
Native: `JVM_MonitorNotifyAll` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/JDK25_LIBS/server/libjvm.so` (sha256 5dffa2b4bcdff59a)  
- nm -D: 0000000000b1ae70 T JVM_MonitorNotifyAll  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.notifyAll -> JVM_MonitorNotifyAll (libjava registers it; HotSpot export)

**S2-12** groovy_5.0.6 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.notify`  
Native: `JVM_MonitorNotify` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/groovy_5.0.6/Dataset/LIBS_groovy_5.0.6/JDK21_LIBS/server/libjvm.so` (sha256 f59cef8ff26a4558)  
- nm -D: 00000000009f3900 T JVM_MonitorNotify  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.notify -> JVM_MonitorNotify (libjava registers it; HotSpot export)

**S2-13** storm_2.4.0-jdk8-buster (jdk8) `[NETTY]` — **correct**: symbol exists and ends with the Java method name; no static table entry  
Java: `io.netty.channel.epoll.LinuxSocket.getPeerCredentials`  
Native: `netty_epoll_linuxsocket_getPeerCredentials` in `~/Tutorial/EchoTrace/Final_results_JDK8/storm_2.4.0-jdk8-buster/Dataset/LIBS_storm_2.4.0-jdk8-buster/libnetty_transport_native_epoll_x86_64.so` (sha256 4059ae0ec61e0707)  
- nm: 0000000000004fd0 t netty_epoll_linuxsocket_getPeerCredentials (local, not exported)  
- rule: Netty symbol naming (netty_<module>_<class>_<method>) for io.netty.channel.epoll.LinuxSocket.getPeerCredentials

**S2-14** cassandra_5.0.8 (latest) `[NETTY]` — **correct**: symbol exists and ends with the Java method name; no static table entry  
Java: `io.netty.channel.epoll.LinuxSocket.sendFile`  
Native: `netty_epoll_linuxsocket_sendFile` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/libnetty_transport_native_epoll_x86_64.so` (sha256 6463e4d1627916e9)  
- nm: 00000000000057b0 t netty_epoll_linuxsocket_sendFile (local, not exported)  
- rule: Netty symbol naming (netty_<module>_<class>_<method>) for io.netty.channel.epoll.LinuxSocket.sendFile

**S2-15** solr_10.0.0 (latest) `[NETTY]` — **correct**: symbol exists and ends with the Java method name; no static table entry  
Java: `io.netty.channel.unix.Socket.recvFrom`  
Native: `netty_unix_socket_recvFrom` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/solr_10.0.0/Dataset/LIBS_solr_10.0.0/libnetty_transport_native_epoll_x86_64.so` (sha256 840fd444f7311ed6)  
- nm: 000000000000a6a0 t netty_unix_socket_recvFrom (local, not exported)  
- rule: Netty symbol naming (netty_<module>_<class>_<method>) for io.netty.channel.unix.Socket.recvFrom

**S2-16** jruby_10.1.0.0 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.notifyAll`  
Native: `JVM_MonitorNotifyAll` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/JDK21_LIBS/server/libjvm.so` (sha256 26d9fefbe1dc56b5)  
- nm -D: 00000000009f39d0 T JVM_MonitorNotifyAll  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.notifyAll -> JVM_MonitorNotifyAll (libjava registers it; HotSpot export)

**S2-17** storm_2.8.8 (latest) `[NETTY]` — **correct**: symbol exists and ends with the Java method name; no static table entry  
Java: `org.apache.storm.shade.io.netty.channel.unix.Socket.recvFromAddress`  
Native: `netty_unix_socket_recvFromAddress` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/storm_2.8.8/Dataset/LIBS_storm_2.8.8/libnetty_transport_native_io_uring42_x86_64.so` (sha256 080883258bd7fca7)  
- nm: 0000000000009e80 t netty_unix_socket_recvFromAddress (local, not exported)  
- rule: Netty symbol naming (netty_<module>_<class>_<method>) for org.apache.storm.shade.io.netty.channel.unix.Socket.recvFromAddress

**S2-18** zookeeper_3.9.5 (latest) `[NETTY]` — **correct**: symbol exists and ends with the Java method name; no static table entry  
Java: `io.netty.channel.epoll.Native.recvmsg0`  
Native: `netty_epoll_native_recvmsg0` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libnetty_transport_native_epoll_x86_64.so` (sha256 6463e4d1627916e9)  
- nm: 00000000000078b0 t netty_epoll_native_recvmsg0 (local, not exported)  
- rule: Netty symbol naming (netty_<module>_<class>_<method>) for io.netty.channel.epoll.Native.recvmsg0

**S2-19** jetty_12.1.10 (latest) `[JVM]` — **correct**: libjvm defines the JVM_* function  
Java: `java.lang.Object.notifyAll`  
Native: `JVM_MonitorNotifyAll` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jetty_12.1.10/Dataset/LIBS_jetty_12.1.10/JDK25_LIBS/server/libjvm.so` (sha256 5dffa2b4bcdff59a)  
- nm -D: 0000000000b1ae70 T JVM_MonitorNotifyAll  
- rule: mapper's built-in table JVM_BUILTIN_NATIVES: java.lang.Object.notifyAll -> JVM_MonitorNotifyAll (libjava registers it; HotSpot export)

**S2-20** cassandra_3.0.29-jdk8-buster (jdk8) `[NETTY]` — **correct**: symbol exists and ends with the Java method name; no static table entry  
Java: `io.netty.channel.epoll.Native.sendmmsg0`  
Native: `netty_epoll_native_sendmmsg0` in `~/Tutorial/EchoTrace/Final_results_JDK8/cassandra_3.0.29-jdk8-buster/Dataset/LIBS_cassandra_3.0.29-jdk8-buster/libnetty-transport-native-epoll.so` (sha256 29f94baa0f2f5b57)  
- nm: 0000000000006e40 t netty_epoll_native_sendmmsg0 (local, not exported)  
- rule: Netty symbol naming (netty_<module>_<class>_<method>) for io.netty.channel.epoll.Native.sendmmsg0


## 3. JNA

**S3-01** cassandra_5.0.8 (latest) `[directmap]` — **correct**: library in the image exports the bound function  
Java: `<org.apache.cassandra.utils.NativeLibraryLinux: com.sun.jna.Pointer strerror(int)>`  
Native: `strerror` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/libc.so.6` (sha256 6b4a45352fd0c540)  
- detector row: directmap | lib 'libc.so.6' | symbol strerror  
- native <org.apache.cassandra.utils.NativeLibraryLinux: com.sun.jna.Pointer strerror(int)>; Native.register(NativeLibrary) (apache-cassandra-5.0.8.jar)  
- nm -D libc.so.6: 000000000009e9d0 T strerror

**S3-02** zookeeper_3.9.5 (latest) `[iface]` — **unverifiable**: other-OS binding (class for another OS); not in a Linux image  
Java: `<org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty: org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty open(org.jline.terminal.spi.TerminalProvider,org.jline.terminal.Attributes,org.jline.terminal.Size)>`  
Native: `openpty` in `` (sha256 )  
- detector row: iface | lib 'util' | symbol openpty  
- call site <org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty: org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty open(org.jline.terminal.spi.TerminalProvider,org.jline.terminal.Attributes,org.jline.terminal.Size)>; Native.load(String,Class); interface method <org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty$UtilLibrary: void openpty(int[],int[],byte[],org.jline.terminal.impl.jna.freebsd.CLibrary$termios,org.jline.terminal.impl.jna.freebsd.CLibrary$winsize)>  
- no libutil in the image

**S3-03** elasticsearch_7.5.2-jdk8-buster (jdk8) `[directmap]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `<org.elasticsearch.bootstrap.JNAKernel32Library: int GetShortPathNameW(com.sun.jna.WString,char[],int)>`  
Native: `GetShortPathNameW` in `` (sha256 )  
- detector row: directmap | lib 'kernel32' | symbol GetShortPathNameW  
- native <org.elasticsearch.bootstrap.JNAKernel32Library: int GetShortPathNameW(com.sun.jna.WString,char[],int)>; Native.register(String) (elasticsearch-7.5.2.jar)  
- Windows library

**S3-04** cassandra_3.0.29-jdk8-buster (jdk8) `[directmap]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `<org.apache.cassandra.utils.NativeLibraryWindows: long GetCurrentProcessId()>`  
Native: `GetCurrentProcessId` in `` (sha256 )  
- detector row: directmap | lib 'kernel32' | symbol GetCurrentProcessId  
- native <org.apache.cassandra.utils.NativeLibraryWindows: long GetCurrentProcessId()>; Native.register(NativeLibrary) (apache-cassandra-3.0.29.jar)  
- Windows library

**S3-05** elasticsearch_7.1.0 (latest) `[directmap]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `<org.elasticsearch.bootstrap.JNAKernel32Library: boolean QueryInformationJobObject(com.sun.jna.Pointer,int,com.sun.jna.Pointer,int,com.sun.jna.Pointer)>`  
Native: `QueryInformationJobObject` in `` (sha256 )  
- detector row: directmap | lib 'kernel32' | symbol QueryInformationJobObject  
- native <org.elasticsearch.bootstrap.JNAKernel32Library: boolean QueryInformationJobObject(com.sun.jna.Pointer,int,com.sun.jna.Pointer,int,com.sun.jna.Pointer)>; Native.register(String) (elasticsearch-7.1.0.jar)  
- Windows library

**S3-06** groovy_5.0.6 (latest) `[iface]` — **correct**: library in the image exports the bound function  
Java: `<org.jline.terminal.impl.jna.linux.LinuxNativePty: void doSetAttr(org.jline.terminal.Attributes)>`  
Native: `tcsetattr` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/groovy_5.0.6/Dataset/LIBS_groovy_5.0.6/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: iface | lib '<?>' | symbol tcsetattr (binding_overrides.tsv: mapped)  
- call site <org.jline.terminal.impl.jna.linux.LinuxNativePty: void doSetAttr(org.jline.terminal.Attributes)>; Native.load(String,Class); interface method <org.jline.terminal.impl.jna.linux.CLibrary: void tcsetattr(int,int,org.jline.terminal.impl.jna.linux.CLibrary$termios)>  
- nm -D libc.so.6: 000000000011cc90 T tcsetattr

**S3-07** cassandra_5.0.8 (latest) `[directmap]` — **unverifiable**: other-OS binding (class for another OS); the Linux library happens to export the name  
Java: `<org.apache.cassandra.utils.NativeLibraryDarwin: int open(java.lang.String,int)>`  
Native: `open` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/libc.so.6` (sha256 6b4a45352fd0c540)  
- detector row: directmap | lib 'libc.so.6' | symbol open  
- native <org.apache.cassandra.utils.NativeLibraryDarwin: int open(java.lang.String,int)>; Native.register(NativeLibrary) (apache-cassandra-5.0.8.jar)  
- nm -D libc.so.6: 00000000000f7fc0 W open

**S3-08** zookeeper_3.9.5 (latest) `[iface]` — **correct**: library in the image exports the bound function  
Java: `<org.jline.terminal.impl.jna.linux.LinuxNativePty: java.lang.String ttyname(int)>`  
Native: `ttyname_r` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libc.so.6` (sha256 c53819710b163d3f)  
- detector row: iface | lib '<?>' | symbol ttyname_r (binding_overrides.tsv: mapped)  
- call site <org.jline.terminal.impl.jna.linux.LinuxNativePty: java.lang.String ttyname(int)>; Native.load(String,Class); interface method <org.jline.terminal.impl.jna.linux.CLibrary: void ttyname_r(int,byte[],int)>  
- nm -D libc.so.6: 0000000000115c50 W ttyname_r

**S3-09** elasticsearch_7.5.2-jdk8-buster (jdk8) `[directmap]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `<org.elasticsearch.bootstrap.JNAKernel32Library: boolean QueryInformationJobObject(com.sun.jna.Pointer,int,com.sun.jna.Pointer,int,com.sun.jna.Pointer)>`  
Native: `QueryInformationJobObject` in `` (sha256 )  
- detector row: directmap | lib 'kernel32' | symbol QueryInformationJobObject  
- native <org.elasticsearch.bootstrap.JNAKernel32Library: boolean QueryInformationJobObject(com.sun.jna.Pointer,int,com.sun.jna.Pointer,int,com.sun.jna.Pointer)>; Native.register(String) (elasticsearch-7.5.2.jar)  
- Windows library

**S3-10** cassandra_3.0.29-jdk8-buster (jdk8) `[directmap]` — **correct**: library in the image exports the bound function  
Java: `<org.apache.cassandra.utils.NativeLibraryLinux: int fsync(int)>`  
Native: `fsync` in `~/Tutorial/EchoTrace/Final_results_JDK8/cassandra_3.0.29-jdk8-buster/Dataset/LIBS_cassandra_3.0.29-jdk8-buster/libc-2.28.so` (sha256 7dcfff73008e9c6e)  
- detector row: directmap | lib 'libc.so.6' | symbol fsync  
- native <org.apache.cassandra.utils.NativeLibraryLinux: int fsync(int)>; Native.register(NativeLibrary) (apache-cassandra-3.0.29.jar)  
- nm -D libc-2.28.so: 00000000000f0da0 T fsync

**S3-11** elasticsearch_7.1.0 (latest) `[iface]` — **unverifiable**: other-OS binding (class for another OS); not in a Linux image  
Java: `<org.elasticsearch.bootstrap.SystemCallFilter: void macImpl(java.nio.file.Path)>`  
Native: `sandbox_init` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/elasticsearch_7.1.0/Dataset/LIBS_elasticsearch_7.1.0/libc-2.17.so` (sha256 690ac7b4b457aa9f)  
- detector row: iface | lib 'libc.so.6' | symbol sandbox_init  
- call site <org.elasticsearch.bootstrap.SystemCallFilter: void macImpl(java.nio.file.Path)>; Native.loadLibrary(String,Class); interface method <org.elasticsearch.bootstrap.SystemCallFilter$MacLibrary: int sandbox_init(java.lang.String,long,com.sun.jna.ptr.PointerByReference)>  
- not exported by libc-2.17.so

**S3-12** groovy_5.0.6 (latest) `[iface]` — **unverifiable**: other-OS binding (class for another OS); the Linux library happens to export the name  
Java: `<org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty: org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty open(org.jline.terminal.spi.TerminalProvider,org.jline.terminal.Attributes,org.jline.terminal.Size)>`  
Native: `openpty` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/groovy_5.0.6/Dataset/LIBS_groovy_5.0.6/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: iface | lib 'libutil.so.1' | symbol openpty  
- call site <org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty: org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty open(org.jline.terminal.spi.TerminalProvider,org.jline.terminal.Attributes,org.jline.terminal.Size)>; Native.load(String,Class); interface method <org.jline.terminal.impl.jna.freebsd.FreeBsdNativePty$UtilLibrary: void openpty(int[],int[],byte[],org.jline.terminal.impl.jna.freebsd.CLibrary$termios,org.jline.terminal.impl.jna.freebsd.CLibrary$winsize)>  
- nm -D libc.so.6: 00000000001836b0 T openpty — exported by libc.so.6, a DT_NEEDED dependency of libutil.so.1 (dlsym on the libutil.so.1 handle resolves it)

**S3-13** cassandra_5.0.8 (latest) `[iface]` — **correct**: library in the image exports the bound function  
Java: `<net.openhft.affinity.impl.LinuxHelper: int syscall(int,java.lang.Object[])>`  
Native: `syscall` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/libc.so.6` (sha256 6b4a45352fd0c540)  
- detector row: iface | lib 'libc.so.6' | symbol syscall  
- call site <net.openhft.affinity.impl.LinuxHelper: int syscall(int,java.lang.Object[])>; Native.load(String,Class); interface method <net.openhft.affinity.impl.LinuxHelper$CLibrary: int syscall(int,java.lang.Object[])>  
- nm -D libc.so.6: 0000000000101810 T syscall

**S3-14** zookeeper_3.9.5 (latest) `[iface]` — **correct**: library in the image exports the bound function  
Java: `<org.jline.terminal.impl.jna.linux.LinuxNativePty: org.jline.terminal.Attributes getAttr()>`  
Native: `tcgetattr` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libc.so.6` (sha256 c53819710b163d3f)  
- detector row: iface | lib '<?>' | symbol tcgetattr (binding_overrides.tsv: mapped)  
- call site <org.jline.terminal.impl.jna.linux.LinuxNativePty: org.jline.terminal.Attributes getAttr()>; Native.load(String,Class); interface method <org.jline.terminal.impl.jna.linux.CLibrary: void tcgetattr(int,org.jline.terminal.impl.jna.linux.CLibrary$termios)>  
- nm -D libc.so.6: 0000000000119fa0 W tcgetattr

**S3-15** elasticsearch_7.5.2-jdk8-buster (jdk8) `[directmap]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `<org.elasticsearch.bootstrap.JNAKernel32Library: boolean SetInformationJobObject(com.sun.jna.Pointer,int,com.sun.jna.Pointer,int)>`  
Native: `SetInformationJobObject` in `` (sha256 )  
- detector row: directmap | lib 'kernel32' | symbol SetInformationJobObject  
- native <org.elasticsearch.bootstrap.JNAKernel32Library: boolean SetInformationJobObject(com.sun.jna.Pointer,int,com.sun.jna.Pointer,int)>; Native.register(String) (elasticsearch-7.5.2.jar)  
- Windows library

**S3-16** cassandra_3.0.29-jdk8-buster (jdk8) `[directmap]` — **unverifiable**: other-OS binding (class for another OS); the Linux library happens to export the name  
Java: `<org.apache.cassandra.utils.NativeLibraryDarwin: com.sun.jna.Pointer strerror(int)>`  
Native: `strerror` in `~/Tutorial/EchoTrace/Final_results_JDK8/cassandra_3.0.29-jdk8-buster/Dataset/LIBS_cassandra_3.0.29-jdk8-buster/libc-2.28.so` (sha256 7dcfff73008e9c6e)  
- detector row: directmap | lib 'libc.so.6' | symbol strerror  
- native <org.apache.cassandra.utils.NativeLibraryDarwin: com.sun.jna.Pointer strerror(int)>; Native.register(NativeLibrary) (apache-cassandra-3.0.29.jar)  
- nm -D libc-2.28.so: 0000000000088000 T strerror

**S3-17** elasticsearch_7.1.0 (latest) `[directmap]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `<org.elasticsearch.bootstrap.JNAKernel32Library: boolean VirtualLock(com.sun.jna.Pointer,org.elasticsearch.bootstrap.JNAKernel32Library$SizeT)>`  
Native: `VirtualLock` in `` (sha256 )  
- detector row: directmap | lib 'kernel32' | symbol VirtualLock  
- native <org.elasticsearch.bootstrap.JNAKernel32Library: boolean VirtualLock(com.sun.jna.Pointer,org.elasticsearch.bootstrap.JNAKernel32Library$SizeT)>; Native.register(String) (elasticsearch-7.1.0.jar)  
- Windows library

**S3-18** groovy_5.0.6 (latest) `[iface]` — **correct**: library in the image exports the bound function  
Java: `<org.jline.terminal.impl.jna.linux.LinuxNativePty: void doSetAttr(org.jline.terminal.Attributes)>`  
Native: `tcgetattr` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/groovy_5.0.6/Dataset/LIBS_groovy_5.0.6/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: iface | lib '<?>' | symbol tcgetattr (binding_overrides.tsv: mapped)  
- call site <org.jline.terminal.impl.jna.linux.LinuxNativePty: void doSetAttr(org.jline.terminal.Attributes)>; Native.load(String,Class); interface method <org.jline.terminal.impl.jna.linux.CLibrary: void tcgetattr(int,org.jline.terminal.impl.jna.linux.CLibrary$termios)>  
- nm -D libc.so.6: 000000000011ce50 W tcgetattr

**S3-19** cassandra_5.0.8 (latest) `[iface]` — **correct**: library in the image exports the bound function  
Java: `<net.openhft.affinity.impl.LinuxHelper: int sched_getcpu()>`  
Native: `sched_getcpu` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/libc.so.6` (sha256 6b4a45352fd0c540)  
- detector row: iface | lib 'libc.so.6' | symbol sched_getcpu  
- call site <net.openhft.affinity.impl.LinuxHelper: int sched_getcpu()>; Native.load(String,Class); interface method <net.openhft.affinity.impl.LinuxHelper$CLibrary: int sched_getcpu()>  
- nm -D libc.so.6: 00000000000f7620 T sched_getcpu

**S3-20** zookeeper_3.9.5 (latest) `[iface]` — **correct**: library in the image exports the bound function  
Java: `<org.jline.terminal.impl.jna.linux.LinuxNativePty: void setSize(org.jline.terminal.Size)>`  
Native: `ioctl` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libc.so.6` (sha256 c53819710b163d3f)  
- detector row: iface | lib '<?>' | symbol ioctl (binding_overrides.tsv: mapped)  
- call site <org.jline.terminal.impl.jna.linux.LinuxNativePty: void setSize(org.jline.terminal.Size)>; Native.load(String,Class); interface method <org.jline.terminal.impl.jna.linux.CLibrary: void ioctl(int,int,org.jline.terminal.impl.jna.linux.CLibrary$winsize)>  
- nm -D libc.so.6: 000000000011a990 W ioctl


## 4. JNR-FFI

**S4-01** cassandra_5.0.8 (latest) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `com.datastax.driver.core.Native$LibCLoader$LibC`  
Native: `gettimeofday` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/libc.so.6` (sha256 6b4a45352fd0c540)  
- detector row: jnr-ffi | lib 'libc.so.6' | symbol gettimeofday  
- interface com.datastax.driver.core.Native$LibCLoader$LibC loaded with LibraryLoader.create().load(String) (cassandra-driver-core-3.12.1-shaded.jar)  
- nm -D libc.so.6: 00000000000c4190 i gettimeofday

**S4-02** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `org.jruby.ext.socket.RubyBasicSocket$LibC`  
Native: `getsockopt` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: jnr-ffi | lib '<?>' | symbol getsockopt (binding_overrides.tsv: mapped)  
- interface org.jruby.ext.socket.RubyBasicSocket$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc.so.6: 000000000012ba90 W getsockopt

**S4-03** jruby_9.4.2.0-jdk8-buster (jdk8) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `jnr.unixsocket.Native$LibC`  
Native: `sendto` in `~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset/LIBS_jruby_9.4.2.0-jdk8-buster/libc-2.28.so` (sha256 5ac376ec4fddf476)  
- detector row: jnr-ffi | lib '<?>' | symbol sendto (binding_overrides.tsv: mapped)  
- interface jnr.unixsocket.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc-2.28.so: 00000000000fa540 W sendto

**S4-04** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `org.jruby.ext.socket.RubyBasicSocket$LibC`  
Native: `setsockopt` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: jnr-ffi | lib '<?>' | symbol setsockopt (binding_overrides.tsv: mapped)  
- interface org.jruby.ext.socket.RubyBasicSocket$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc.so.6: 000000000012c180 W setsockopt

**S4-05** jruby_9.4.2.0-jdk8-buster (jdk8) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `jnr.unixsocket.Native$LibC`  
Native: `listen` in `~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset/LIBS_jruby_9.4.2.0-jdk8-buster/libc-2.28.so` (sha256 5ac376ec4fddf476)  
- detector row: jnr-ffi | lib '<?>' | symbol listen (binding_overrides.tsv: mapped)  
- interface jnr.unixsocket.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc-2.28.so: 00000000000fa190 W listen

**S4-06** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `jnr.enxio.channels.Native$LibC`  
Native: `fcntl` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: jnr-ffi | lib 'socket' | symbol fcntl  
- interface jnr.enxio.channels.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc.so.6: 0000000000117000 W fcntl

**S4-07** jruby_9.4.2.0-jdk8-buster (jdk8) `[jnr-ffi]` — **unverifiable**: other-OS binding (BSD/macOS function); not in a Linux image  
Java: `jnr.enxio.channels.Native$LibC`  
Native: `kevent` in `~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset/LIBS_jruby_9.4.2.0-jdk8-buster/libc-2.28.so` (sha256 5ac376ec4fddf476)  
- detector row: jnr-ffi | lib 'socket' | symbol kevent  
- interface jnr.enxio.channels.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- not exported by libc-2.28.so

**S4-08** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `jnr.unixsocket.Native$LibC`  
Native: `socket` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: jnr-ffi | lib '<?>' | symbol socket (binding_overrides.tsv: mapped)  
- interface jnr.unixsocket.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc.so.6: 000000000012c310 W socket

**S4-09** jruby_9.4.2.0-jdk8-buster (jdk8) `[jnr-ffi]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `org.jruby.util.WindowsFFI$Kernel32`  
Native: `OpenProcess` in `` (sha256 )  
- detector row: jnr-ffi | lib 'Kernel32' | symbol OpenProcess  
- interface org.jruby.util.WindowsFFI$Kernel32 loaded with LibraryLoader.create().load(String) (jruby.jar)  
- Windows library

**S4-10** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `jnr.enxio.channels.Native$LibC`  
Native: `write` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: jnr-ffi | lib 'socket' | symbol write  
- interface jnr.enxio.channels.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc.so.6: 000000000011c590 W write

**S4-11** jruby_9.4.2.0-jdk8-buster (jdk8) `[jnr-ffi]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `org.jruby.util.WindowsFFI$Kernel32`  
Native: `GetProcessId` in `` (sha256 )  
- detector row: jnr-ffi | lib 'Kernel32' | symbol GetProcessId  
- interface org.jruby.util.WindowsFFI$Kernel32 loaded with LibraryLoader.create().load(String) (jruby.jar)  
- Windows library

**S4-12** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `jnr.enxio.channels.Native$LibC`  
Native: `read` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: jnr-ffi | lib 'socket' | symbol read  
- interface jnr.enxio.channels.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc.so.6: 000000000011ba80 T read

**S4-13** jruby_9.4.2.0-jdk8-buster (jdk8) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `jnr.unixsocket.Native$LibC`  
Native: `connect` in `~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset/LIBS_jruby_9.4.2.0-jdk8-buster/libc-2.28.so` (sha256 5ac376ec4fddf476)  
- detector row: jnr-ffi | lib '<?>' | symbol connect (binding_overrides.tsv: mapped)  
- interface jnr.unixsocket.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc-2.28.so: 00000000000fa060 W connect

**S4-14** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `org.jruby.util.WindowsFFI$Kernel32`  
Native: `OpenProcess` in `` (sha256 )  
- detector row: jnr-ffi | lib 'Kernel32' | symbol OpenProcess  
- interface org.jruby.util.WindowsFFI$Kernel32 loaded with LibraryLoader.create().load(String) (jruby.jar)  
- Windows library

**S4-15** jruby_9.4.2.0-jdk8-buster (jdk8) `[jnr-ffi]` — **unverifiable**: other-OS binding (BSD/macOS function); not in a Linux image  
Java: `jnr.enxio.channels.Native$LibC`  
Native: `kqueue` in `~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset/LIBS_jruby_9.4.2.0-jdk8-buster/libc-2.28.so` (sha256 5ac376ec4fddf476)  
- detector row: jnr-ffi | lib 'socket' | symbol kqueue  
- interface jnr.enxio.channels.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- not exported by libc-2.28.so

**S4-16** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **unverifiable**: other-OS binding (BSD/macOS function); not in a Linux image  
Java: `jnr.enxio.channels.Native$LibC`  
Native: `kevent` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: jnr-ffi | lib 'socket' | symbol kevent  
- interface jnr.enxio.channels.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- not exported by libc.so.6

**S4-17** jruby_9.4.2.0-jdk8-buster (jdk8) `[jnr-ffi]` — **unverifiable**: other-OS binding (Windows library); not in a Linux image  
Java: `org.jruby.util.WindowsFFI$Kernel32`  
Native: `CloseHandle` in `` (sha256 )  
- detector row: jnr-ffi | lib 'Kernel32' | symbol CloseHandle  
- interface org.jruby.util.WindowsFFI$Kernel32 loaded with LibraryLoader.create().load(String) (jruby.jar)  
- Windows library

**S4-18** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `jnr.unixsocket.Native$LibC`  
Native: `bind` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: jnr-ffi | lib '<?>' | symbol bind (binding_overrides.tsv: mapped)  
- interface jnr.unixsocket.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc.so.6: 000000000012b960 W bind

**S4-19** jruby_9.4.2.0-jdk8-buster (jdk8) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `org.jruby.ext.socket.RubyBasicSocket$LibC`  
Native: `getsockopt` in `~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset/LIBS_jruby_9.4.2.0-jdk8-buster/libc-2.28.so` (sha256 5ac376ec4fddf476)  
- detector row: jnr-ffi | lib '<?>' | symbol getsockopt (binding_overrides.tsv: mapped)  
- interface org.jruby.ext.socket.RubyBasicSocket$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc-2.28.so: 00000000000fa160 W getsockopt

**S4-20** jruby_10.1.0.0 (latest) `[jnr-ffi]` — **correct**: library in the image exports the bound function  
Java: `jnr.unixsocket.Native$LibC`  
Native: `fcntl` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libc.so.6` (sha256 d8db8739a1633c97)  
- detector row: jnr-ffi | lib '<?>' | symbol fcntl (binding_overrides.tsv: mapped)  
- interface jnr.unixsocket.Native$LibC loaded with LibraryLoader.create().library().load() (jruby.jar)  
- nm -D libc.so.6: 0000000000117000 W fcntl


## 5. FFM

**S5-01** zookeeper_3.9.5 (latest) `[ffi]` — **correct (library note)**: function correct; the detector's library name is imprecise (not in libutil (absent from the image))  
Java: `<org.jline.terminal.impl.ffm.CLibrary: void setAttributes(int,org.jline.terminal.Attributes)>`  
Native: `tcsetattr` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libc.so.6` (sha256 c53819710b163d3f)  
- detector row: ffi | lib 'util' | symbol tcsetattr  
- <org.jline.terminal.impl.ffm.CLibrary: void setAttributes(int,org.jline.terminal.Attributes)> via downcallHandle (jline-3.25.1.jar)  
- nm -D libc.so.6: 0000000000119db0 T tcsetattr — not in libutil (absent from the image); exported by libc.so.6 (Linker default lookup)

**S5-02** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function  
Java: `<org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment SSL_get0_peer_certificate(java.lang.foreign.MemorySegment)>`  
Native: `SSL_get0_peer_certificate` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libssl.so.3` (sha256 0ca2c28b026f0084)  
- detector row: ffi | lib 'ssl' | symbol SSL_get0_peer_certificate  
- <org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment SSL_get0_peer_certificate(java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libssl.so.3: 0000000000035fd0 T SSL_get0_peer_certificate

**S5-03** zookeeper_3.9.5 (latest) `[ffi]` — **correct (library note)**: function correct; the detector's library name is imprecise (not in libutil (absent from the image))  
Java: `<org.jline.terminal.impl.ffm.CLibrary: java.lang.String ttyName(int)>`  
Native: `ttyname_r` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libc.so.6` (sha256 c53819710b163d3f)  
- detector row: ffi | lib 'util' | symbol ttyname_r  
- <org.jline.terminal.impl.ffm.CLibrary: java.lang.String ttyName(int)> via downcallHandle (jline-3.25.1.jar)  
- nm -D libc.so.6: 0000000000115c50 W ttyname_r — not in libutil (absent from the image); exported by libc.so.6 (Linker default lookup)

**S5-04** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function  
Java: `<org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment SSL_get_peer_cert_chain(java.lang.foreign.MemorySegment)>`  
Native: `SSL_get_peer_cert_chain` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libssl.so.3` (sha256 0ca2c28b026f0084)  
- detector row: ffi | lib 'ssl' | symbol SSL_get_peer_cert_chain  
- <org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment SSL_get_peer_cert_chain(java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libssl.so.3: 0000000000036030 T SSL_get_peer_cert_chain

**S5-05** zookeeper_3.9.5 (latest) `[ffi]` — **correct (library note)**: function correct; the detector's library name is imprecise (not in libutil (absent from the image))  
Java: `<org.jline.terminal.impl.ffm.CLibrary: org.jline.terminal.Attributes getAttributes(int)>`  
Native: `tcgetattr` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libc.so.6` (sha256 c53819710b163d3f)  
- detector row: ffi | lib 'util' | symbol tcgetattr  
- <org.jline.terminal.impl.ffm.CLibrary: org.jline.terminal.Attributes getAttributes(int)> via downcallHandle (jline-3.25.1.jar)  
- nm -D libc.so.6: 0000000000119fa0 W tcgetattr — not in libutil (absent from the image); exported by libc.so.6 (Linker default lookup)

**S5-06** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function through a dependency  
Java: `<org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment X509_STORE_add_lookup(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)>`  
Native: `X509_STORE_add_lookup` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libcrypto.so.3` (sha256 e6391daf670544d3)  
- detector row: ffi | lib 'ssl' | symbol X509_STORE_add_lookup  
- <org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment X509_STORE_add_lookup(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libcrypto.so.3: 000000000037c270 T X509_STORE_add_lookup — exported by libcrypto.so.3, a DT_NEEDED dependency of libssl.so.3 (dlsym on the libssl.so.3 handle resolves it)

**S5-07** zookeeper_3.9.5 (latest) `[ffi]` — **correct (library note)**: function correct; the detector's library name is imprecise (not in libutil (absent from the image))  
Java: `<org.jline.terminal.impl.ffm.CLibrary: org.jline.terminal.spi.Pty openpty(org.jline.terminal.spi.TerminalProvider,org.jline.terminal.Attributes,org.jline.terminal.Size)>`  
Native: `openpty` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libc.so.6` (sha256 c53819710b163d3f)  
- detector row: ffi | lib 'util' | symbol openpty  
- <org.jline.terminal.impl.ffm.CLibrary: org.jline.terminal.spi.Pty openpty(org.jline.terminal.spi.TerminalProvider,org.jline.terminal.Attributes,org.jline.terminal.Size)> via downcallHandle (jline-3.25.1.jar)  
- nm -D libc.so.6: 00000000001741b0 T openpty — not in libutil (absent from the image); exported by libc.so.6 (Linker default lookup)

**S5-08** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function  
Java: `<org.apache.tomcat.util.openssl.openssl_h: int SSL_CTX_use_certificate_chain_file(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)>`  
Native: `SSL_CTX_use_certificate_chain_file` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libssl.so.3` (sha256 0ca2c28b026f0084)  
- detector row: ffi | lib 'ssl' | symbol SSL_CTX_use_certificate_chain_file  
- <org.apache.tomcat.util.openssl.openssl_h: int SSL_CTX_use_certificate_chain_file(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libssl.so.3: 000000000003ffd0 T SSL_CTX_use_certificate_chain_file

**S5-09** zookeeper_3.9.5 (latest) `[ffi]` — **correct (library note)**: function correct; the detector's library name is imprecise (not in libutil (absent from the image))  
Java: `<org.jline.terminal.impl.ffm.CLibrary: boolean isTty(int)>`  
Native: `isatty` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libc.so.6` (sha256 c53819710b163d3f)  
- detector row: ffi | lib 'util' | symbol isatty  
- <org.jline.terminal.impl.ffm.CLibrary: boolean isTty(int)> via downcallHandle (jline-3.25.1.jar)  
- nm -D libc.so.6: 0000000000115fb0 W isatty — not in libutil (absent from the image); exported by libc.so.6 (Linker default lookup)

**S5-10** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function through a dependency  
Java: `<org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment ASN1_STRING_get0_data(java.lang.foreign.MemorySegment)>`  
Native: `ASN1_STRING_get0_data` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libcrypto.so.3` (sha256 e6391daf670544d3)  
- detector row: ffi | lib 'ssl' | symbol ASN1_STRING_get0_data  
- <org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment ASN1_STRING_get0_data(java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libcrypto.so.3: 00000000000d5820 T ASN1_STRING_get0_data — exported by libcrypto.so.3, a DT_NEEDED dependency of libssl.so.3 (dlsym on the libssl.so.3 handle resolves it)

**S5-11** zookeeper_3.9.5 (latest) `[ffi]` — **correct (library note)**: function correct; the detector's library name is imprecise (not in libutil (absent from the image))  
Java: `<org.jline.terminal.impl.ffm.CLibrary: void setTerminalSize(int,org.jline.terminal.Size)>`  
Native: `ioctl` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/libc.so.6` (sha256 c53819710b163d3f)  
- detector row: ffi | lib 'util' | symbol ioctl  
- <org.jline.terminal.impl.ffm.CLibrary: void setTerminalSize(int,org.jline.terminal.Size)> via downcallHandle (jline-3.25.1.jar)  
- nm -D libc.so.6: 000000000011a990 W ioctl — not in libutil (absent from the image); exported by libc.so.6 (Linker default lookup)

**S5-12** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function through a dependency  
Java: `<org.apache.tomcat.util.openssl.openssl_h: int X509_STORE_CTX_get_error_depth(java.lang.foreign.MemorySegment)>`  
Native: `X509_STORE_CTX_get_error_depth` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libcrypto.so.3` (sha256 e6391daf670544d3)  
- detector row: ffi | lib 'ssl' | symbol X509_STORE_CTX_get_error_depth  
- <org.apache.tomcat.util.openssl.openssl_h: int X509_STORE_CTX_get_error_depth(java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libcrypto.so.3: 0000000000384e70 T X509_STORE_CTX_get_error_depth — exported by libcrypto.so.3, a DT_NEEDED dependency of libssl.so.3 (dlsym on the libssl.so.3 handle resolves it)

**S5-13** tomcat_11.0.22 (latest) `[ffi]` — **unverifiable**: version-conditional binding (BoringSSL / OpenSSL 1.x name); the image's OpenSSL 3 does not export it and Tomcat does not call it there  
Java: `<org.apache.tomcat.util.openssl.openssl_h_Compatibility: int EVP_PKEY_bits(java.lang.foreign.MemorySegment)>`  
Native: `EVP_PKEY_bits` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libssl.so.3` (sha256 0ca2c28b026f0084)  
- detector row: ffi | lib 'ssl' | symbol EVP_PKEY_bits  
- <org.apache.tomcat.util.openssl.openssl_h_Compatibility: int EVP_PKEY_bits(java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- not exported by libssl.so.3  
- bytecode: the downcall is taken only for another SSL library (openssl_h_Macros: if BORINGSSL, else the macro via SSL_CTX_ctrl; openssl_h_Compatibility: OpenSSL 1.x / LibreSSL names, e.g. EVP_PKEY_bits = EVP_PKEY_get_bits in OpenSSL 3)

**S5-14** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function through a dependency  
Java: `<org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment OCSP_REQUEST_new()>`  
Native: `OCSP_REQUEST_new` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libcrypto.so.3` (sha256 e6391daf670544d3)  
- detector row: ffi | lib 'ssl' | symbol OCSP_REQUEST_new  
- <org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment OCSP_REQUEST_new()> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libcrypto.so.3: 00000000002e8850 T OCSP_REQUEST_new — exported by libcrypto.so.3, a DT_NEEDED dependency of libssl.so.3 (dlsym on the libssl.so.3 handle resolves it)

**S5-15** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function  
Java: `<org.apache.tomcat.util.openssl.openssl_h: int SSL_CTX_set_ciphersuites(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)>`  
Native: `SSL_CTX_set_ciphersuites` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libssl.so.3` (sha256 0ca2c28b026f0084)  
- detector row: ffi | lib 'ssl' | symbol SSL_CTX_set_ciphersuites  
- <org.apache.tomcat.util.openssl.openssl_h: int SSL_CTX_set_ciphersuites(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libssl.so.3: 0000000000030100 T SSL_CTX_set_ciphersuites

**S5-16** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function through a dependency  
Java: `<org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment EVP_MD_get0_provider(java.lang.foreign.MemorySegment)>`  
Native: `EVP_MD_get0_provider` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libcrypto.so.3` (sha256 e6391daf670544d3)  
- detector row: ffi | lib 'ssl' | symbol EVP_MD_get0_provider  
- <org.apache.tomcat.util.openssl.openssl_h: java.lang.foreign.MemorySegment EVP_MD_get0_provider(java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libcrypto.so.3: 00000000001fd2b0 T EVP_MD_get0_provider — exported by libcrypto.so.3, a DT_NEEDED dependency of libssl.so.3 (dlsym on the libssl.so.3 handle resolves it)

**S5-17** tomcat_11.0.22 (latest) `[ffi]` — **unverifiable**: version-conditional binding (BoringSSL / OpenSSL 1.x name); the image's OpenSSL 3 does not export it and Tomcat does not call it there  
Java: `<org.apache.tomcat.util.openssl.openssl_h_Macros: long SSL_CTX_set1_groups_list(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)>`  
Native: `SSL_CTX_set1_groups_list` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libssl.so.3` (sha256 0ca2c28b026f0084)  
- detector row: ffi | lib 'ssl' | symbol SSL_CTX_set1_groups_list  
- <org.apache.tomcat.util.openssl.openssl_h_Macros: long SSL_CTX_set1_groups_list(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- not exported by libssl.so.3  
- bytecode: the downcall is taken only for another SSL library (openssl_h_Macros: if BORINGSSL, else the macro via SSL_CTX_ctrl; openssl_h_Compatibility: OpenSSL 1.x / LibreSSL names, e.g. EVP_PKEY_bits = EVP_PKEY_get_bits in OpenSSL 3)

**S5-18** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function through a dependency  
Java: `<org.apache.tomcat.util.openssl.openssl_h: int i2d_X509(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)>`  
Native: `i2d_X509` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libcrypto.so.3` (sha256 e6391daf670544d3)  
- detector row: ffi | lib 'ssl' | symbol i2d_X509  
- <org.apache.tomcat.util.openssl.openssl_h: int i2d_X509(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libcrypto.so.3: 000000000038e8e0 T i2d_X509 — exported by libcrypto.so.3, a DT_NEEDED dependency of libssl.so.3 (dlsym on the libssl.so.3 handle resolves it)

**S5-19** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function through a dependency  
Java: `<org.apache.tomcat.util.openssl.openssl_h: int BIO_read(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment,int)>`  
Native: `BIO_read` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libcrypto.so.3` (sha256 e6391daf670544d3)  
- detector row: ffi | lib 'ssl' | symbol BIO_read  
- <org.apache.tomcat.util.openssl.openssl_h: int BIO_read(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment,int)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libcrypto.so.3: 00000000000edcc0 T BIO_read — exported by libcrypto.so.3, a DT_NEEDED dependency of libssl.so.3 (dlsym on the libssl.so.3 handle resolves it)

**S5-20** tomcat_11.0.22 (latest) `[ffi]` — **correct**: library in the image exports the bound function  
Java: `<org.apache.tomcat.util.openssl.openssl_h: void SSL_CTX_set_default_passwd_cb(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)>`  
Native: `SSL_CTX_set_default_passwd_cb` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libssl.so.3` (sha256 0ca2c28b026f0084)  
- detector row: ffi | lib 'ssl' | symbol SSL_CTX_set_default_passwd_cb  
- <org.apache.tomcat.util.openssl.openssl_h: void SSL_CTX_set_default_passwd_cb(java.lang.foreign.MemorySegment,java.lang.foreign.MemorySegment)> via downcallHandle (tomcat-coyote-ffm.jar)  
- nm -D libssl.so.3: 00000000000384e0 T SSL_CTX_set_default_passwd_cb


## 6. manual / supplied library

**S6-01** elasticsearch_7.1.0 (latest) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `jdk.internal.misc.Unsafe.registerNatives`  
Native: `JVM_RegisterJDKInternalMiscUnsafeMethods` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/elasticsearch_7.1.0/Dataset/LIBS_elasticsearch_7.1.0/JDK12_LIBS/server/libjvm.so` (sha256 91223359e6796b47)  
- manual mapping line (notfound_search/libjvm.so) [JVM]  
- nm: 0000000000e081a0 t JVM_RegisterJDKInternalMiscUnsafeMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-02** cassandra_5.0.8 (latest) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `jdk.internal.misc.Unsafe.registerNatives`  
Native: `JVM_RegisterJDKInternalMiscUnsafeMethods` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/libjvm.so` (sha256 7d064a0dbf29c8ca)  
- manual mapping line (LIBS_cassandra_5.0.8/libjvm.so) [JVM]  
- nm: 0000000000e9ff60 t JVM_RegisterJDKInternalMiscUnsafeMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-03** groovy_5.0.6 (latest) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `jdk.internal.perf.Perf.registerNatives`  
Native: `JVM_RegisterPerfMethods` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/groovy_5.0.6/Dataset/LIBS_groovy_5.0.6/libjvm.so` (sha256 f59cef8ff26a4558)  
- manual mapping line (LIBS_groovy_5.0.6/libjvm.so) [JVM]  
- nm: 0000000000d567b0 t JVM_RegisterPerfMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-04** elasticsearch_7.5.2-jdk8-buster (jdk8) `[JNI]` — **correct**: symbol defined in the image's library  
Java: `org.elasticsearch.bootstrap.JNACLibrary.geteuid`  
Native: `geteuid` in `~/Tutorial/EchoTrace/Final_results_JDK8/elasticsearch_7.5.2-jdk8-buster/Dataset_symbolized/LIBS_elasticsearch_7.5.2-jdk8-buster/libc-2.28.so` (sha256 82680100dc6a0d79)  
- manual mapping line (~/Tutorial/EchoTrace/Final_results_JDK8/elasticsearch_7.5.2-jdk8-buster/Dataset_symbolized/LIBS_elasticsearch_7.5.2-jdk8-buster/libc.so.6) [JNI]  
- nm -D: 00000000000c7340 W geteuid  
- library is the image's own file (mapped in the supplement run)  
- JNA direct-mapped native: libc function named geteuid: match

**S6-05** tomcat_7.0-jdk8-buster (jdk8) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `java.lang.invoke.MethodHandleNatives.registerNatives`  
Native: `JVM_RegisterMethodHandleMethods` in `~/Tutorial/EchoTrace/Final_results_JDK8/tomcat_7.0-jdk8-buster/Dataset_symbolized/LIBS_tomcat_7.0-jdk8-buster/libjvm.so` (sha256 da71c35e28da3257)  
- manual mapping line (~/Tutorial/EchoTrace/Final_results_JDK8/tomcat_7.0-jdk8-buster/Dataset_symbolized/LIBS_tomcat_7.0-jdk8-buster/libjvm.so) [JVM]  
- nm: 000000000090ff00 t JVM_RegisterMethodHandleMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-06** storm_2.8.8 (latest) `[REGISTERED]` — **correct (version note)**: function correct; library not loaded by the app at run time (see provenance)  
Java: `org.apache.storm.shade.io.netty.channel.uring.Native.ioUringEnter`  
Native: `netty_io_uring_enter` in `~/Tutorial/EchoTrace_latest/unavailable_libs/storm_2.8.8/io_uring/libnetty_transport_native_io_uring42_x86_64.so` (sha256 080883258bd7fca7)  
- manual mapping line (unavailable_libs/storm_2.8.8/io_uring/libnetty_transport_native_io_uring42_x86_64.so) [REGISTERED]  
- nm: 0000000000005be0 t netty_io_uring_enter (local, not exported)  
- provenance: /home/rupesh.punna/Tutorial/EchoTrace_latest/Final_results_latest_versions/storm_2.8.8/Dataset_symbolized/LIBS_storm_2.8.8/libnetty_transport_native_io_uring42_x86_64.so — netty 4.2.12 io_uring (symbolized), from storm-shaded-deps-2.8.8.jar; mapped by user decision (2026-11-06) although storm cannot load it (registers unshaded io/netty/channel/uring/*); same symbols as the June storm_latest run  
- RegisterNatives entry: libnetty_transport_native_io_uring42_x86_64.so vaddr 0x139c0 (file offset 0x129c0): {"ioUringEnter", "(IIII)I", 0x5be0 (netty_io_uring_enter)}

**S6-07** tomcat_11.0.22 (latest) `[JNI]` — **correct (version note)**: function correct; supplied library documented in NOTES.md (not shipped by the image)  
Java: `jdk.internal.foreign.abi.fallback.LibFallback.ffi_type_void`  
Native: `Java_jdk_internal_foreign_abi_fallback_LibFallback_ffi_1type_1void` in `~/Tutorial/EchoTrace_latest/unavailable_libs/tomcat_11.0.22/openjdk-25.0.3-fallbackLinker/libfallbackLinker.so` (sha256 b86bad2b65b302c9)  
- manual mapping line (openjdk-25.0.3-fallbackLinker/libfallbackLinker.so) [JNI]  
- nm -D: 00000000000027b0 T Java_jdk_internal_foreign_abi_fallback_LibFallback_ffi_1type_1void  
- library: ~/Tutorial/EchoTrace_latest/unavailable_libs/tomcat_11.0.22/openjdk-25.0.3-fallbackLinker/libfallbackLinker.so (no PROVENANCE.tsv row)  
- expected JNI name Java_jdk_internal_foreign_abi_fallback_LibFallback_ffi_1type_1void: match  
- provenance (unavailable_libs/NOTES.md): libfallbackLinker.so built from openjdk/jdk25u jdk-25.0.3+9 (_downloads/libfallbackLinker-jdk-25.0.3+9; libffi.so.8 alongside);

**S6-08** jetty_9.4.51-jdk8-buster (jdk8) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `sun.misc.Unsafe.registerNatives`  
Native: `JVM_RegisterUnsafeMethods` in `~/Tutorial/EchoTrace/Final_results_JDK8/jetty_9.4.51-jdk8-buster/Dataset_symbolized/LIBS_jetty_9.4.51-jdk8-buster/libjvm.so` (sha256 da71c35e28da3257)  
- manual mapping line (~/Tutorial/EchoTrace/Final_results_JDK8/jetty_9.4.51-jdk8-buster/Dataset_symbolized/LIBS_jetty_9.4.51-jdk8-buster/libjvm.so) [JVM]  
- nm: 0000000000b10450 t JVM_RegisterUnsafeMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-09** zookeeper_3.4.14-jdk8-buster (jdk8) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `jdk.jfr.internal.JVM.getClassId`  
Native: `jfr_class_id` in `~/Tutorial/EchoTrace/Final_results_JDK8/zookeeper_3.4.14-jdk8-buster/Dataset_symbolized/LIBS_zookeeper_3.4.14-jdk8-buster/libjvm.so` (sha256 da71c35e28da3257)  
- manual mapping line (~/Tutorial/EchoTrace/Final_results_JDK8/zookeeper_3.4.14-jdk8-buster/Dataset_symbolized/LIBS_zookeeper_3.4.14-jdk8-buster/libjvm.so) [JVM]  
- nm: 00000000006c8380 t jfr_class_id (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-10** jruby_9.4.2.0-jdk8-buster (jdk8) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `sun.misc.Perf.createLong`  
Native: `Perf_CreateLong` in `~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset_symbolized/LIBS_jruby_9.4.2.0-jdk8-buster/libjvm.so` (sha256 da71c35e28da3257)  
- manual mapping line (~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset_symbolized/LIBS_jruby_9.4.2.0-jdk8-buster/libjvm.so) [JVM]  
- nm: 00000000009b7580 t Perf_CreateLong (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-11** orientdb_3.2.19-jdk8-buster (jdk8) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `sun.misc.Unsafe.registerNatives`  
Native: `JVM_RegisterUnsafeMethods` in `~/Tutorial/EchoTrace/Final_results_JDK8/orientdb_3.2.19-jdk8-buster/Dataset_symbolized/LIBS_orientdb_3.2.19-jdk8-buster/libjvm.so` (sha256 da71c35e28da3257)  
- manual mapping line (~/Tutorial/EchoTrace/Final_results_JDK8/orientdb_3.2.19-jdk8-buster/Dataset_symbolized/LIBS_orientdb_3.2.19-jdk8-buster/libjvm.so) [JVM]  
- nm: 0000000000b10450 t JVM_RegisterUnsafeMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-12** cassandra_3.0.29-jdk8-buster (jdk8) `[NETTY]` — **correct**: symbol defined in the image's library  
Java: `io.netty.channel.unix.Socket.getPeerCredentials`  
Native: `netty_channel_unix_socket_getPeerCredentials` in `~/Tutorial/EchoTrace/Final_results_JDK8/cassandra_3.0.29-jdk8-buster/Dataset_symbolized/LIBS_cassandra_3.0.29-jdk8-buster/libnetty-transport-native-epoll.so` (sha256 29f94baa0f2f5b57)  
- manual mapping line (~/Tutorial/EchoTrace/Final_results_JDK8/cassandra_3.0.29-jdk8-buster/Dataset_symbolized/LIBS_cassandra_3.0.29-jdk8-buster/libnetty-transport-native-epoll.so) [NETTY]  
- nm: 0000000000005700 t netty_channel_unix_socket_getPeerCredentials (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-13** solr_10.0.0 (latest) `[JNI_DYNAMIC]` — **correct**: symbol defined in the library of the matching version  
Java: `io.netty.internal.tcnative.SSL.getLastErrorNumber`  
Native: `netty_internal_tcnative_SSL_getLastErrorNumber` in `~/Tutorial/EchoTrace_latest/unavailable_libs/solr_10.0.0/libnetty_tcnative_linux_x86_64.so` (sha256 ec0fe8ed43699c52)  
- manual mapping line (unavailable_libs/solr_10.0.0/libnetty_tcnative_linux_x86_64.so) [JNI_DYNAMIC]  
- nm: 000000000002e770 t netty_internal_tcnative_SSL_getLastErrorNumber (local, not exported)  
- provenance: /home/rupesh.punna/Prototype/Final_results_echotrace/cassandra_5.0.6-bookworm/Dataset/LIBS_cassandra_5.0.6-bookworm/libnetty_tcnative_linux_x86_64.so — netty-tcnative 2.0.70.Final linux-x86_64; byte-identical to Prototype solr_slim copy; solr 10 ships only the classes jar for 2.0.70  
- RegisterNatives entry: libnetty_tcnative_linux_x86_64.so vaddr 0x23e628 (file offset 0x23d628): {"getLastErrorNumber", "()I", 0x2e770 (netty_internal_tcnative_SSL_getLastErrorNumber)}

**S6-14** jruby_10.1.0.0 (latest) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `jdk.internal.perf.Perf.registerNatives`  
Native: `JVM_RegisterPerfMethods` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/libjvm.so` (sha256 26d9fefbe1dc56b5)  
- manual mapping line (LIBS_jruby_10.1.0.0/libjvm.so) [JVM]  
- nm: 0000000000d567b0 t JVM_RegisterPerfMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-15** jetty_12.1.10 (latest) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `jdk.internal.perf.Perf.registerNatives`  
Native: `JVM_RegisterPerfMethods` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jetty_12.1.10/Dataset/LIBS_jetty_12.1.10/libjvm.so` (sha256 5dffa2b4bcdff59a)  
- manual mapping line (LIBS_jetty_12.1.10/libjvm.so) [JVM]  
- nm: 0000000000ebae20 t JVM_RegisterPerfMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-16** solr_8.7.0-jdk8-buster (jdk8) `[JNI_DYNAMIC]` — **correct**: symbol defined in the library of the matching version  
Java: `io.netty.channel.epoll.Native.eventFd`  
Native: `netty_epoll_native_eventFd` in `~/Tutorial/EchoTrace_latest/unavailable_libs/solr_8.7.0-jdk8-buster/libnetty_transport_native_epoll_x86_64.so` (sha256 029bed26e682ce00)  
- manual mapping line (libnetty_transport_native_epoll_x86_64.so) [JNI_DYNAMIC]  
- nm: 0000000000004c90 t netty_epoll_native_eventFd (local, not exported)  
- provenance: https://repo1.maven.org/maven2/io/netty/netty-transport-native-epoll/4.1.50.Final/netty-transport-native-epoll-4.1.50.Final-linux-x86_64.jar — netty-transport-native-epoll 4.1.50.Final linux-x86_64 (sha1 checked against Maven Central); byte-identical to ~/Prototype/netty_libs_all/libnetty_epoll_4.1.50.Final.jar.so; solr ships only the classes jar  
- RegisterNatives entry: libnetty_transport_native_epoll_x86_64.so vaddr 0x20e5e0 (file offset 0xe5e0): {"eventFd", "()I", 0x4c90 (netty_epoll_native_eventFd)}

**S6-17** storm_2.4.0-jdk8-buster (jdk8) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `jdk.jfr.internal.JVM.registerNatives`  
Native: `jfr_register_natives` in `~/Tutorial/EchoTrace/Final_results_JDK8/storm_2.4.0-jdk8-buster/Dataset_symbolized/LIBS_storm_2.4.0-jdk8-buster/libjvm.so` (sha256 da71c35e28da3257)  
- manual mapping line (~/Tutorial/EchoTrace/Final_results_JDK8/storm_2.4.0-jdk8-buster/Dataset_symbolized/LIBS_storm_2.4.0-jdk8-buster/libjvm.so) [JVM]  
- nm: 00000000006c72d0 t jfr_register_natives (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-18** orientdb_3.2.53 (latest) `[JNI]` — **correct**: symbol defined in the library of the matching version  
Java: `com.kenai.jffi.Foreign.getByteArrayChecked`  
Native: `Java_com_kenai_jffi_Foreign_getByteArrayChecked` in `~/Tutorial/EchoTrace_latest/unavailable_libs/orientdb_3.2.53/libjffi-1.2.so` (sha256 2f9ea4c923c6b7ee)  
- manual mapping line (unavailable_libs/orientdb_3.2.53/libjffi-1.2.so) [JNI]  
- nm -D: 000000000000bbe0 T Java_com_kenai_jffi_Foreign_getByteArrayChecked  
- provenance: /home/rupesh.punna/Tutorial/EchoTrace_latest/Final_results_latest_versions/orientdb_3.2.53/Dataset/JARFILES_orientdb_3.2.53/jffi-1.3.9-native.jar!/jni/x86_64-Linux/libjffi-1.2.so — from the target's own jffi native jar (exact version)  
- expected JNI name Java_com_kenai_jffi_Foreign_getByteArrayChecked: match

**S6-19** zookeeper_3.9.5 (latest) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `java.lang.invoke.MethodHandleNatives.registerNatives`  
Native: `JVM_RegisterMethodHandleMethods` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/JDK17_LIBS/server/libjvm.so` (sha256 7d064a0dbf29c8ca)  
- manual mapping line (notfound_search/libjvm.so) [JVM]  
- nm: 0000000000bc4900 t JVM_RegisterMethodHandleMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)

**S6-20** groovy_4.0.0-jdk8-buster (jdk8) `[JVM]` — **correct**: symbol defined in the image's library  
Java: `java.lang.invoke.MethodHandleNatives.registerNatives`  
Native: `JVM_RegisterMethodHandleMethods` in `~/Tutorial/EchoTrace/Final_results_JDK8/groovy_4.0.0-jdk8-buster/Dataset_symbolized/LIBS_groovy_4.0.0-jdk8-buster/libjvm.so` (sha256 da71c35e28da3257)  
- manual mapping line (~/Tutorial/EchoTrace/Final_results_JDK8/groovy_4.0.0-jdk8-buster/Dataset_symbolized/LIBS_groovy_4.0.0-jdk8-buster/libjvm.so) [JVM]  
- nm: 000000000090ff00 t JVM_RegisterMethodHandleMethods (local, not exported)  
- library is the image's own file (mapped in the supplement run)


## 7. control: JNI symbol lookup

**S7-01** groovy_5.0.6 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.lang.Class.isAssignableFrom`  
Native: `Java_java_lang_Class_isAssignableFrom` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/groovy_5.0.6/Dataset/LIBS_groovy_5.0.6/JDK21_LIBS/libjava.so` (sha256 cdcb1ce2b9352f21)  
- expected short name Java_java_lang_Class_isAssignableFrom  
- nm -D: 000000000000e960 T Java_java_lang_Class_isAssignableFrom

**S7-02** jruby_10.1.0.0 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.lang.StackStreamFactory$AbstractStackWalker.callStackWalk`  
Native: `Java_java_lang_StackStreamFactory_00024AbstractStackWalker_callStackWalk` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jruby_10.1.0.0/Dataset/LIBS_jruby_10.1.0.0/JDK21_LIBS/libjava.so` (sha256 ddccf070f3d797e1)  
- expected short name Java_java_lang_StackStreamFactory_00024AbstractStackWalker_callStackWalk  
- nm -D: 0000000000013260 T Java_java_lang_StackStreamFactory_00024AbstractStackWalker_callStackWalk

**S7-03** storm_2.8.8 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `sun.nio.ch.Net.joinOrDrop6`  
Native: `Java_sun_nio_ch_Net_joinOrDrop6` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/storm_2.8.8/Dataset/LIBS_storm_2.8.8/libnio.so` (sha256 fcfcc573468080ae)  
- expected short name Java_sun_nio_ch_Net_joinOrDrop6  
- nm -D: 000000000000b060 T Java_sun_nio_ch_Net_joinOrDrop6

**S7-04** orientdb_3.2.19-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `com.kenai.jffi.Foreign.munmap`  
Native: `Java_com_kenai_jffi_Foreign_munmap` in `~/Tutorial/EchoTrace/Final_results_JDK8/orientdb_3.2.19-jdk8-buster/Dataset/LIBS_orientdb_3.2.19-jdk8-buster/libjffi-1.2.so` (sha256 9c38610250738359)  
- expected short name Java_com_kenai_jffi_Foreign_munmap  
- nm -D: 000000000000bee0 T Java_com_kenai_jffi_Foreign_munmap

**S7-05** elasticsearch_7.5.2-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.util.zip.Inflater.reset`  
Native: `Java_java_util_zip_Inflater_reset` in `~/Tutorial/EchoTrace/Final_results_JDK8/elasticsearch_7.5.2-jdk8-buster/Dataset/LIBS_elasticsearch_7.5.2-jdk8-buster/libzip.so` (sha256 f08a0938c666d174)  
- expected short name Java_java_util_zip_Inflater_reset  
- nm -D: 0000000000003630 T Java_java_util_zip_Inflater_reset

**S7-06** orientdb_3.2.53 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `com.kenai.jffi.Foreign.getTypeSize`  
Native: `Java_com_kenai_jffi_Foreign_getTypeSize` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/orientdb_3.2.53/Dataset/LIBS_orientdb_3.2.53/libjffi-1.2.so` (sha256 9c38610250738359)  
- expected short name Java_com_kenai_jffi_Foreign_getTypeSize  
- nm -D: 000000000000cb40 T Java_com_kenai_jffi_Foreign_getTypeSize

**S7-07** zookeeper_3.4.14-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `sun.nio.ch.FileChannelImpl.unmap0`  
Native: `Java_sun_nio_ch_FileChannelImpl_unmap0` in `~/Tutorial/EchoTrace/Final_results_JDK8/zookeeper_3.4.14-jdk8-buster/Dataset/LIBS_zookeeper_3.4.14-jdk8-buster/libnio.so` (sha256 3ec3e6f8c3e0c7e5)  
- expected short name Java_sun_nio_ch_FileChannelImpl_unmap0  
- nm -D: 0000000000007590 T Java_sun_nio_ch_FileChannelImpl_unmap0

**S7-08** elasticsearch_7.1.0 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.net.SocketInputStream.init`  
Native: `Java_java_net_SocketInputStream_init` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/elasticsearch_7.1.0/Dataset/LIBS_elasticsearch_7.1.0/JDK12_LIBS/libnet.so` (sha256 a88a548aed4dd647)  
- expected short name Java_java_net_SocketInputStream_init  
- nm -D: 000000000000df40 T Java_java_net_SocketInputStream_init

**S7-09** zookeeper_3.9.5 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `sun.awt.X11.XlibWrapper.XFilterEvent`  
Native: `Java_sun_awt_X11_XlibWrapper_XFilterEvent` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/zookeeper_3.9.5/Dataset/LIBS_zookeeper_3.9.5/JDK17_LIBS/libawt_xawt.so` (sha256 6b201fd498de094d)  
- expected short name Java_sun_awt_X11_XlibWrapper_XFilterEvent  
- nm -D: 0000000000031660 T Java_sun_awt_X11_XlibWrapper_XFilterEvent

**S7-10** tomcat_7.0-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `org.apache.tomcat.jni.Directory.make`  
Native: `Java_org_apache_tomcat_jni_Directory_make` in `~/Tutorial/EchoTrace/Final_results_JDK8/tomcat_7.0-jdk8-buster/Dataset/LIBS_tomcat_7.0-jdk8-buster/libtcnative-1.so.0.2.28` (sha256 41d4942d4ae15d92)  
- expected short name Java_org_apache_tomcat_jni_Directory_make  
- nm -D: 00000000000124c0 T Java_org_apache_tomcat_jni_Directory_make

**S7-11** tomcat_11.0.22 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `sun.nio.ch.NativeSocketAddress.offsetSin4Port`  
Native: `Java_sun_nio_ch_NativeSocketAddress_offsetSin4Port` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/tomcat_11.0.22/Dataset/LIBS_tomcat_11.0.22/libnio.so` (sha256 7ecb9696fc2a4fff)  
- expected short name Java_sun_nio_ch_NativeSocketAddress_offsetSin4Port  
- nm -D: 000000000000a730 T Java_sun_nio_ch_NativeSocketAddress_offsetSin4Port

**S7-12** solr_10.0.0 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `sun.nio.ch.Net.pollerrValue`  
Native: `Java_sun_nio_ch_Net_pollerrValue` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/solr_10.0.0/Dataset/LIBS_solr_10.0.0/libnio.so` (sha256 bc444112121aaa00)  
- expected short name Java_sun_nio_ch_Net_pollerrValue  
- nm -D: 000000000000c660 T Java_sun_nio_ch_Net_pollerrValue

**S7-13** cassandra_3.0.29-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.io.UnixFileSystem.createDirectory`  
Native: `Java_java_io_UnixFileSystem_createDirectory` in `~/Tutorial/EchoTrace/Final_results_JDK8/cassandra_3.0.29-jdk8-buster/Dataset/LIBS_cassandra_3.0.29-jdk8-buster/libjava.so` (sha256 85faa73de027e5a4)  
- expected short name Java_java_io_UnixFileSystem_createDirectory  
- nm -D: 0000000000016680 T Java_java_io_UnixFileSystem_createDirectory

**S7-14** groovy_4.0.0-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.util.zip.ZipFile.getEntryBytes`  
Native: `Java_java_util_zip_ZipFile_getEntryBytes` in `~/Tutorial/EchoTrace/Final_results_JDK8/groovy_4.0.0-jdk8-buster/Dataset/LIBS_groovy_4.0.0-jdk8-buster/JDK8_LIBS/amd64/libzip.so` (sha256 f08a0938c666d174)  
- expected short name Java_java_util_zip_ZipFile_getEntryBytes  
- nm -D: 0000000000003ac0 T Java_java_util_zip_ZipFile_getEntryBytes

**S7-15** storm_2.4.0-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `org.rocksdb.RocksDB.keyMayExist`  
Native: `Java_org_rocksdb_RocksDB_keyMayExist__J_3BIIJLjava_lang_StringBuilder_2` in `~/Tutorial/EchoTrace/Final_results_JDK8/storm_2.4.0-jdk8-buster/Dataset/LIBS_storm_2.4.0-jdk8-buster/librocksdbjni6329444148818420541.so` (sha256 dfccaa38a2e40877)  
- expected short name Java_org_rocksdb_RocksDB_keyMayExist (overloaded form: + __<mangled args>)  
- nm -D: 00000000001a0bb0 T Java_org_rocksdb_RocksDB_keyMayExist__J_3BIIJLjava_lang_StringBuilder_2

**S7-16** jetty_9.4.51-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.lang.System.setOut0`  
Native: `Java_java_lang_System_setOut0` in `~/Tutorial/EchoTrace/Final_results_JDK8/jetty_9.4.51-jdk8-buster/Dataset/LIBS_jetty_9.4.51-jdk8-buster/JDK8_LIBS/amd64/libjava.so` (sha256 85faa73de027e5a4)  
- expected short name Java_java_lang_System_setOut0  
- nm -D: 00000000000145a0 T Java_java_lang_System_setOut0

**S7-17** jruby_9.4.2.0-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.lang.reflect.Proxy.defineClass0`  
Native: `Java_java_lang_reflect_Proxy_defineClass0` in `~/Tutorial/EchoTrace/Final_results_JDK8/jruby_9.4.2.0-jdk8-buster/Dataset/LIBS_jruby_9.4.2.0-jdk8-buster/JDK8_LIBS/amd64/libjava.so` (sha256 85faa73de027e5a4)  
- expected short name Java_java_lang_reflect_Proxy_defineClass0  
- nm -D: 0000000000011110 T Java_java_lang_reflect_Proxy_defineClass0

**S7-18** jetty_12.1.10 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.lang.ProcessImpl.init`  
Native: `Java_java_lang_ProcessImpl_init` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/jetty_12.1.10/Dataset/LIBS_jetty_12.1.10/libjava.so` (sha256 0ae08e6f61a2fcae)  
- expected short name Java_java_lang_ProcessImpl_init  
- nm -D: 00000000000123e0 T Java_java_lang_ProcessImpl_init

**S7-19** solr_8.7.0-jdk8-buster (jdk8) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `sun.net.dns.ResolverConfigurationImpl.fallbackDomain0`  
Native: `Java_sun_net_dns_ResolverConfigurationImpl_fallbackDomain0` in `~/Tutorial/EchoTrace/Final_results_JDK8/solr_8.7.0-jdk8-buster/Dataset/LIBS_solr_8.7.0-jdk8-buster/JDK8_LIBS/amd64/libnet.so` (sha256 03d43cc88f18502c)  
- expected short name Java_sun_net_dns_ResolverConfigurationImpl_fallbackDomain0  
- nm -D: 000000000000ea10 T Java_sun_net_dns_ResolverConfigurationImpl_fallbackDomain0

**S7-20** cassandra_5.0.8 (latest) `[JNI]` — **correct**: mangled name matches and the library defines it  
Java: `java.lang.Float.intBitsToFloat`  
Native: `Java_java_lang_Float_intBitsToFloat` in `~/Tutorial/EchoTrace_latest/Final_results_latest_versions/cassandra_5.0.8/Dataset/LIBS_cassandra_5.0.8/libjava.so` (sha256 a1dde1cc24d629d6)  
- expected short name Java_java_lang_Float_intBitsToFloat  
- nm -D: 0000000000010420 T Java_java_lang_Float_intBitsToFloat

